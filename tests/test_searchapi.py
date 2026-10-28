"""Contract and failure tests: every SearchApi HTTP request is mocked."""

from unittest.mock import Mock

import pytest
import requests

from src.youtubedoc.searchapi import SearchApiClient, SearchApiError


VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
API_KEY = "test-searchapi-secret-do-not-log"
LANGUAGE_ERROR = "Selected language hasn't been transcribed. Check `available_languages`."


def response(payload, status=200):
    result = Mock()
    result.status_code = status
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(f"unsafe {API_KEY}")
    return result


@pytest.fixture
def http(monkeypatch):
    get = Mock()
    monkeypatch.setattr("src.youtubedoc.searchapi.requests.get", get)
    return get


@pytest.fixture
def client():
    return SearchApiClient(API_KEY)


def test_video_fields_are_normalized_without_exposing_provider_payload(client, http):
    http.return_value = response({
        "video": {
            "id": VIDEO_ID,
            "title": "A useful tutorial",
            "description": "Learn something new.",
            "length_seconds": 321,
            "views": 12345,
            "author": "Example creator",
            "published_time": "May 7, 2020",
            "thumbnail": "https://i.ytimg.com/vi/example.jpg",
        },
        "search_metadata": {"status": "Success", "request_url": "not-for-output"},
        "search_parameters": {"api_key": API_KEY},
    })

    assert client.get_video_info(VIDEO_ID, VIDEO_URL) == {
        "title": "A useful tutorial",
        "description": "Learn something new.",
        "duration": 321,
        "view_count": 12345,
        "channel": "Example creator",
        "upload_date": "20200507",
        "url": VIDEO_URL,
        "video_id": VIDEO_ID,
        "thumbnail_url": "https://i.ytimg.com/vi/example.jpg",
    }
    args, kwargs = http.call_args
    assert args == ("https://www.searchapi.io/api/v1/search",)
    assert kwargs["params"] == {"engine": "youtube_video", "video_id": VIDEO_ID}
    assert kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert kwargs["timeout"] == (5, 20)
    assert kwargs["allow_redirects"] is False
    assert API_KEY not in repr(kwargs["params"])


def test_video_uses_channel_name_when_author_missing(client, http):
    http.return_value = response({"video": {"title": "Tutorial"}, "channel": {"name": "Channel name"}})
    info = client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert info["channel"] == "Channel name"
    assert info["duration"] == 0
    assert info["view_count"] is None
    assert info["upload_date"] is None


@pytest.mark.parametrize("published,expected", [
    ("May 7, 2020", "20200507"),
    ("2020-05-07", "20200507"),
    ("3 days ago", None),
    (None, None),
])
def test_video_date_is_normalized_only_when_known(client, http, published, expected):
    http.return_value = response({"video": {"title": "Tutorial", "published_time": published}})
    assert client.get_video_info(VIDEO_ID, VIDEO_URL)["upload_date"] == expected


@pytest.mark.parametrize("payload", [
    None, [], "not an object", {}, {"video": None}, {"video": []},
    {"video": {"title": ""}}, {"video": {"title": "   "}},
    {"video": {"title": 123}}, {"error": "private provider detail"},
])
def test_invalid_video_payloads_fail_safely(client, http, payload):
    http.return_value = response(payload)
    with pytest.raises(SearchApiError):
        client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert http.call_count == 1


def test_transcript_lines_language_and_request_contract(client, http):
    http.return_value = response({"transcripts": [
        {"text": "Bonjour", "start": 0.15, "duration": 1.2},
        {"text": "le monde", "start": 1.35, "duration": 2.0},
    ]})
    assert client.get_transcript(VIDEO_ID, "fr", 1000) == ("Bonjour\nle monde", "fr")
    assert http.call_args.kwargs["params"] == {
        "engine": "youtube_transcripts", "video_id": VIDEO_ID, "lang": "fr",
    }
    assert http.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert http.call_args.kwargs["timeout"] == (5, 20)
    assert http.call_args.kwargs["allow_redirects"] is False


def test_transcript_keeps_existing_character_truncation_marker(client, http):
    http.return_value = response({"transcripts": [{"text": "abcdefghijk"}]})
    assert client.get_transcript(VIDEO_ID, "en", 5) == ("abcde\n[Transcript truncated...]", "en")


@pytest.mark.parametrize("limit", [0, None])
def test_no_limit_preserves_full_transcript(client, http, limit):
    http.return_value = response({"transcripts": [{"text": "First"}, {"text": "Second"}]})
    assert client.get_transcript(VIDEO_ID, "en", limit) == ("First\nSecond", "en")


@pytest.mark.parametrize("payload", [
    {}, {"transcripts": []}, {"transcripts": None}, {"transcripts": {}},
    {"transcripts": [None]}, {"transcripts": ["text"]},
    {"transcripts": [{"text": None}]}, {"transcripts": [{"text": 42}]},
    {"transcripts": [{"text": ""}]}, {"transcripts": [{"text": "  \n  "}]},
    {"transcripts": [{"text": "valid"}, {"wrong": "invalid"}]},
])
def test_invalid_or_empty_transcripts_are_not_reported_as_success(client, http, payload):
    http.return_value = response(payload)
    with pytest.raises(SearchApiError):
        client.get_transcript(VIDEO_ID, "en", 1000)
    assert http.call_count == 1


def test_unavailable_requested_language_retries_one_known_language(client, http):
    http.side_effect = [
        response({"error": LANGUAGE_ERROR, "available_languages": [
            None, {}, {"lang": ""}, {"name": "French", "lang": "fr"}, {"lang": "de"},
        ]}),
        response({"transcripts": [{"text": "Bonjour"}]}),
    ]
    assert client.get_transcript(VIDEO_ID, "en", 1000) == ("Bonjour", "fr")
    assert [c.kwargs["params"]["lang"] for c in http.call_args_list] == ["en", "fr"]


def test_language_fallback_never_repeats_the_requested_language(client, http):
    http.side_effect = [
        response({"error": LANGUAGE_ERROR, "available_languages": [{"lang": "en"}, {"lang": "de"}]}),
        response({"transcripts": [{"text": "Hallo"}]}),
    ]
    assert client.get_transcript(VIDEO_ID, "en", 1000) == ("Hallo", "de")
    assert http.call_count == 2


def test_language_fallback_is_bounded_to_one_extra_request(client, http):
    http.side_effect = [
        response({"error": LANGUAGE_ERROR, "available_languages": [{"lang": "fr"}]}),
        response({"error": LANGUAGE_ERROR, "available_languages": [{"lang": "de"}]}),
    ]
    with pytest.raises(SearchApiError):
        client.get_transcript(VIDEO_ID, "en", 1000)
    assert http.call_count == 2


@pytest.mark.parametrize("available", [None, [], "fr", {}, [{"lang": "en"}], [{"lang": 123}]])
def test_language_error_without_a_valid_alternative_does_not_retry(client, http, available):
    http.return_value = response({"error": LANGUAGE_ERROR, "available_languages": available})
    with pytest.raises(SearchApiError):
        client.get_transcript(VIDEO_ID, "en", 1000)
    assert http.call_count == 1


@pytest.mark.parametrize("status", [301, 302, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("method", ["video", "transcript"])
def test_http_errors_do_not_retry_or_leak_response_details(client, http, status, method, capsys, caplog):
    http.return_value = response({"error": API_KEY, "available_languages": [{"lang": "fr"}]}, status)
    with pytest.raises(SearchApiError) as exc:
        if method == "video":
            client.get_video_info(VIDEO_ID, VIDEO_URL)
        else:
            client.get_transcript(VIDEO_ID, "en", 1000)
    assert http.call_count == 1
    assert API_KEY not in str(exc.value)
    assert API_KEY not in capsys.readouterr().out + caplog.text


@pytest.mark.parametrize("error", [requests.Timeout, requests.ConnectionError, requests.RequestException])
def test_transport_errors_are_sanitized_and_not_retried(client, http, error):
    http.side_effect = error(f"unsafe request detail {API_KEY}")
    with pytest.raises(SearchApiError) as exc:
        client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert API_KEY not in str(exc.value)
    assert http.call_count == 1


def test_invalid_json_is_sanitized(client, http):
    http.return_value = response(None)
    http.return_value.json.side_effect = ValueError(f"unsafe response {API_KEY}")
    with pytest.raises(SearchApiError) as exc:
        client.get_transcript(VIDEO_ID, "en", 1000)
    assert API_KEY not in str(exc.value)
    assert http.call_count == 1


def test_provider_error_with_languages_is_not_a_license_to_retry(client, http):
    http.return_value = response({"error": f"Invalid API key: {API_KEY}", "available_languages": [{"lang": "fr"}]})
    with pytest.raises(SearchApiError) as exc:
        client.get_transcript(VIDEO_ID, "en", 1000)
    assert API_KEY not in str(exc.value)
    assert http.call_count == 1


@pytest.mark.parametrize("value", [True, False, -1, "123", [], float("nan"), 1.5])
def test_invalid_numeric_metadata_cannot_pollute_downstream_output(client, http, value):
    http.return_value = response({"video": {"title": "Tutorial", "length_seconds": value, "views": value}})
    info = client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert info["duration"] == 0
    assert info["view_count"] is None


def test_zero_numeric_metadata_is_preserved(client, http):
    http.return_value = response({"video": {"title": "Tutorial", "length_seconds": 0, "views": 0}})
    info = client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert info["duration"] == 0
    assert info["view_count"] == 0


def test_malformed_optional_metadata_fields_use_safe_defaults(client, http):
    http.return_value = response({
        "video": {"title": "Tutorial", "description": [], "author": {}, "published_time": [], "thumbnail": 123},
        "channel": [],
    })
    info = client.get_video_info(VIDEO_ID, VIDEO_URL)
    assert info["description"] == ""
    assert info["channel"] == "Unknown Channel"
    assert info["upload_date"] is None
    assert info["thumbnail_url"] == f"https://img.youtube.com/vi/{VIDEO_ID}/maxresdefault.jpg"


@pytest.mark.parametrize("method", ["video", "transcript"])
def test_search_metadata_failure_status_is_not_success(client, http, method):
    http.return_value = response({
        "search_metadata": {"status": "Error"},
        "video": {"title": "Unreliable data"},
        "transcripts": [{"text": "Unreliable data"}],
    })
    with pytest.raises(SearchApiError):
        if method == "video":
            client.get_video_info(VIDEO_ID, VIDEO_URL)
        else:
            client.get_transcript(VIDEO_ID, "en", 1000)


@pytest.mark.parametrize("key", ["", " \t\n "])
def test_empty_client_key_never_makes_an_http_request(http, key):
    with pytest.raises(SearchApiError):
        SearchApiClient(key).get_video_info(VIDEO_ID, VIDEO_URL)
    http.assert_not_called()


@pytest.mark.parametrize("status", [200, 401, 429, 500])
def test_http_responses_are_closed_on_success_and_error(client, http, status):
    http.return_value = response({"video": {"title": "Tutorial"}}, status)
    if status == 200:
        client.get_video_info(VIDEO_ID, VIDEO_URL)
    else:
        with pytest.raises(SearchApiError):
            client.get_video_info(VIDEO_ID, VIDEO_URL)
    http.return_value.close.assert_called_once()


def test_invalid_json_response_is_closed(client, http):
    http.return_value = response(None)
    http.return_value.json.side_effect = ValueError("invalid JSON")
    with pytest.raises(SearchApiError):
        client.get_video_info(VIDEO_ID, VIDEO_URL)
    http.return_value.close.assert_called_once()
