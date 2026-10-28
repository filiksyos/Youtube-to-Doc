"""Exercise real HTTP routes with all external services mocked."""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from src.server import query_processor
from src.server.main import app
from src.server.server_utils import limiter
from src.youtubedoc import youtube_processor
from src.youtubedoc.utils import s3_uploader


VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
KEY = "fake-server-only-key"


@pytest.fixture
def fallback_client(monkeypatch):
    limiter.reset()
    monkeypatch.setenv("SEARCHAPI_API_KEY", KEY)
    monkeypatch.setattr(youtube_processor, "yt_dlp", None)
    monkeypatch.setattr(youtube_processor, "YouTube", None)
    monkeypatch.setattr(
        youtube_processor.YoutubeProcessor,
        "_get_transcript_youtube_api",
        AsyncMock(return_value=(None, None)),
    )
    # Do not access S3 or download tiktoken's encoding during isolated tests.
    monkeypatch.setattr(s3_uploader, "check_cached_documentation", Mock(return_value=None))
    monkeypatch.setattr(s3_uploader, "upload_markdown_to_s3", Mock(return_value=None))
    monkeypatch.setattr(query_processor, "upload_markdown_to_s3", Mock(return_value=None))
    monkeypatch.setattr(query_processor, "_estimate_tokens", lambda text: len(text) // 4)

    def response(payload, status_code=200):
        result = Mock(status_code=status_code)
        result.json.return_value = payload
        return result

    http = Mock(side_effect=[
        response({"video": {"title": "Fallback title", "length_seconds": 75, "author": "Creator"}}),
        response({"transcripts": [{"text": "Bonjour"}, {"text": "tout le monde"}]}),
    ])
    monkeypatch.setattr("src.youtubedoc.searchapi.requests.get", http)
    with TestClient(app, base_url="http://localhost") as client:
        yield client, http, response


def stream_events(client):
    response = client.get("/api/process/stream", params={"url": VIDEO_URL, "language": "fr"})
    assert response.status_code == 200
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_stream_generates_clean_fallback_documentation(fallback_client):
    client, http, _ = fallback_client
    events = stream_events(client)
    assert not any(event["status"] == "error" for event in events)
    transcript_event = next(event for event in events if event["status"] == "transcript_done")
    assert transcript_event["length"] == len("Bonjour\ntout le monde")
    content = events[-1]["content"]
    assert events[-1]["status"] == "complete"
    assert "**Title:** Fallback title" in content
    assert "**Duration:** 1m 15s" in content
    assert "**Transcript Language:** fr" in content
    assert "## Transcript\nBonjour\ntout le monde" in content
    assert "('Bonjour" not in content
    assert KEY not in json.dumps(events)
    assert http.call_count == 2


def test_stream_keeps_existing_missing_content_behavior(fallback_client):
    client, http, response = fallback_client
    http.side_effect = [response({"error": KEY}, 429), response({"error": KEY}, 401)]
    events = stream_events(client)
    assert events[-1]["status"] == "complete"
    transcript_event = next(event for event in events if event["status"] == "transcript_done")
    assert transcript_event["length"] == 0
    content = events[-1]["content"]
    assert f"**Title:** Video {VIDEO_ID}" in content
    assert "## Transcript" not in content
    assert "(None, None)" not in content
    assert KEY not in json.dumps(events)
    assert http.call_count == 2


def test_cached_stream_does_not_call_searchapi(fallback_client, monkeypatch):
    client, http, _ = fallback_client
    cached_url = "https://example.com/cached-doc.md"
    monkeypatch.setattr(s3_uploader, "check_cached_documentation", lambda key: cached_url)
    events = stream_events(client)
    assert events[-1]["content_url"] == cached_url
    assert events[-1]["cached"] is True
    http.assert_not_called()


def test_stream_rate_limit_prevents_additional_processing(fallback_client, monkeypatch):
    client, http, _ = fallback_client
    cache_check = Mock(return_value="https://example.com/cached-doc.md")
    monkeypatch.setattr(s3_uploader, "check_cached_documentation", cache_check)
    for _ in range(5):
        assert client.get("/api/process/stream", params={"url": VIDEO_URL}).status_code == 200
    blocked = client.get("/api/process/stream", params={"url": VIDEO_URL})
    assert blocked.status_code == 429
    assert cache_check.call_count == 5
    http.assert_not_called()


def test_form_post_includes_fallback_metadata_and_transcript(fallback_client):
    client, http, _ = fallback_client
    response = client.post("/", data={"input_text": VIDEO_URL})
    assert response.status_code == 200
    assert "Fallback title" in response.text
    assert "Bonjour" in response.text
    assert "tout le monde" in response.text
    assert KEY not in response.text
    assert http.call_count == 2


def test_invalid_video_url_never_calls_searchapi(fallback_client):
    client, http, _ = fallback_client
    response = client.get("/api/process/stream", params={"url": "https://example.com/not-youtube"})
    assert '"status": "error"' in response.text
    assert KEY not in response.text
    http.assert_not_called()
