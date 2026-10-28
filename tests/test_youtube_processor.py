"""Provider-order integration tests; no YouTube or SearchApi network calls."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.youtubedoc import youtube_processor as module
from src.youtubedoc.schemas.video_schema import VideoQuery
from src.youtubedoc.searchapi import SearchApiError


VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


@pytest.fixture
def processor(monkeypatch):
    monkeypatch.delenv("SEARCHAPI_API_KEY", raising=False)
    monkeypatch.setattr(module, "yt_dlp", None)
    monkeypatch.setattr(module, "YouTube", None)
    monkeypatch.setattr(module, "YouTubeTranscriptApi", None)
    monkeypatch.setattr(module.YoutubeProcessor, "_check_dependencies", lambda self: None)
    monkeypatch.setattr(module.YoutubeProcessor, "_log_proxy_env_state", lambda self: None)
    # Any accidentally unmocked SearchApi network request fails this test.
    monkeypatch.setattr("src.youtubedoc.searchapi.requests.get", Mock(side_effect=AssertionError("Unexpected HTTP request")))
    return module.YoutubeProcessor()


def enable_searchapi(processor):
    processor.searchapi = Mock()
    processor.searchapi.get_video_info.return_value = {"title": "SearchApi title"}
    processor.searchapi.get_transcript.return_value = ("SearchApi transcript", "fr")
    return processor.searchapi


@pytest.mark.parametrize("key", [None, "", "   "])
def test_unconfigured_key_disables_searchapi(monkeypatch, processor, key):
    if key is None:
        monkeypatch.delenv("SEARCHAPI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("SEARCHAPI_API_KEY", key)
    factory = Mock()
    monkeypatch.setattr(module, "SearchApiClient", factory)
    new_processor = module.YoutubeProcessor()
    assert new_processor.searchapi is None
    factory.assert_not_called()


def test_configured_key_creates_server_side_client(monkeypatch, processor):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "  server-only-key  ")
    factory = Mock()
    monkeypatch.setattr(module, "SearchApiClient", factory)
    new_processor = module.YoutubeProcessor()
    factory.assert_called_once_with("server-only-key")
    assert new_processor.searchapi is factory.return_value


def test_ytdlp_success_does_not_call_pytube_or_searchapi(monkeypatch, processor):
    monkeypatch.setattr(module, "yt_dlp", Mock())
    monkeypatch.setattr(module, "YouTube", Mock())
    searchapi = enable_searchapi(processor)
    processor._get_video_info_yt_dlp = AsyncMock(return_value={"title": "Original"})
    processor._get_video_info_pytube = AsyncMock()
    assert asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL)) == {"title": "Original"}
    processor._get_video_info_pytube.assert_not_awaited()
    searchapi.get_video_info.assert_not_called()


def test_pytube_success_after_ytdlp_failure_does_not_call_searchapi(monkeypatch, processor):
    monkeypatch.setattr(module, "yt_dlp", Mock())
    monkeypatch.setattr(module, "YouTube", Mock())
    searchapi = enable_searchapi(processor)
    processor._get_video_info_yt_dlp = AsyncMock(side_effect=RuntimeError("blocked"))
    processor._get_video_info_pytube = AsyncMock(return_value={"title": "Pytube"})
    assert asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL)) == {"title": "Pytube"}
    processor._get_video_info_yt_dlp.assert_awaited_once_with(VIDEO_ID, VIDEO_URL)
    processor._get_video_info_pytube.assert_awaited_once_with(VIDEO_URL)
    searchapi.get_video_info.assert_not_called()


def test_metadata_provider_order_is_ytdlp_then_pytube_then_searchapi(monkeypatch, processor):
    monkeypatch.setattr(module, "yt_dlp", Mock())
    monkeypatch.setattr(module, "YouTube", Mock())
    order = []

    async def ytdlp(*args):
        order.append("yt-dlp")
        raise RuntimeError("blocked")

    async def pytube(*args):
        order.append("pytube")
        raise RuntimeError("blocked")

    def fallback(*args):
        order.append("searchapi")
        return {"title": "Fallback"}

    processor._get_video_info_yt_dlp = ytdlp
    processor._get_video_info_pytube = pytube
    searchapi = enable_searchapi(processor)
    searchapi.get_video_info.side_effect = fallback
    assert asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL)) == {"title": "Fallback"}
    assert order == ["yt-dlp", "pytube", "searchapi"]


def test_missing_metadata_dependencies_still_allow_searchapi(processor):
    searchapi = enable_searchapi(processor)
    assert asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL)) == {"title": "SearchApi title"}
    searchapi.get_video_info.assert_called_once_with(VIDEO_ID, VIDEO_URL)


def test_unconfigured_metadata_preserves_minimal_result(processor):
    info = asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL))
    assert info["title"] == f"Video {VIDEO_ID}"
    assert info["video_id"] == VIDEO_ID
    assert info["url"] == VIDEO_URL


def test_failed_metadata_fallback_preserves_minimal_result(processor):
    searchapi = enable_searchapi(processor)
    searchapi.get_video_info.side_effect = SearchApiError("SearchApi request failed")
    info = asyncio.run(processor._get_video_info(VIDEO_ID, VIDEO_URL))
    assert info["title"] == f"Video {VIDEO_ID}"
    searchapi.get_video_info.assert_called_once()


def test_primary_transcript_success_never_uses_searchapi(processor):
    searchapi = enable_searchapi(processor)
    processor._get_transcript_youtube_api = AsyncMock(return_value=("Primary transcript", "en"))
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == ("Primary transcript", "en")
    processor._get_transcript_youtube_api.assert_awaited_once_with(VIDEO_ID, "en", 500)
    searchapi.get_transcript.assert_not_called()


@pytest.mark.parametrize("primary_result", [(None, None), ("", "en"), ("   ", "en")])
def test_no_usable_primary_transcript_invokes_searchapi(processor, primary_result):
    searchapi = enable_searchapi(processor)
    processor._get_transcript_youtube_api = AsyncMock(return_value=primary_result)
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == ("SearchApi transcript", "fr")
    searchapi.get_transcript.assert_called_once_with(VIDEO_ID, "en", 500)


def test_missing_transcript_dependency_uses_searchapi(processor):
    searchapi = enable_searchapi(processor)
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == ("SearchApi transcript", "fr")
    searchapi.get_transcript.assert_called_once_with(VIDEO_ID, "en", 500)


def test_missing_formatter_uses_searchapi(monkeypatch, processor):
    monkeypatch.setattr(module, "YouTubeTranscriptApi", Mock())
    processor.text_formatter = None
    searchapi = enable_searchapi(processor)
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == ("SearchApi transcript", "fr")
    searchapi.get_transcript.assert_called_once_with(VIDEO_ID, "en", 500)


def test_unconfigured_transcript_preserves_unavailable_result(processor):
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == (None, None)


def test_failed_transcript_fallback_preserves_unavailable_result(processor):
    searchapi = enable_searchapi(processor)
    searchapi.get_transcript.side_effect = SearchApiError("SearchApi request failed")
    assert asyncio.run(processor._get_transcript(VIDEO_ID, "en", 500)) == (None, None)
    searchapi.get_transcript.assert_called_once()


def test_process_video_passes_fallback_language_through(processor):
    processor._get_video_info = AsyncMock(return_value={"title": "Fallback video"})
    processor._get_transcript = AsyncMock(return_value=("Bonjour", "fr"))
    processor._get_comments = AsyncMock()
    query = VideoQuery(url=VIDEO_URL, language="en", max_transcript_length=500)
    info, transcript, comments = asyncio.run(processor.process_video(query))
    assert info["detected_transcript_language"] == "fr"
    assert transcript == "Bonjour"
    assert comments is None
    processor._get_comments.assert_not_awaited()
