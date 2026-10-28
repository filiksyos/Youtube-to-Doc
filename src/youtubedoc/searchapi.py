"""Optional SearchApi fallback. Only the server holds the API key.

API contracts: https://www.searchapi.io/docs/youtube-video and
https://www.searchapi.io/docs/youtube-transcripts
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests


class SearchApiError(Exception):
    """A safe error message, without provider bodies, credentials or request URLs."""


class SearchApiClient:
    """Small synchronous client, called in a worker thread by YoutubeProcessor."""

    URL = "https://www.searchapi.io/api/v1/search"
    TIMEOUT = (5, 20)  # Connection and read timeout, in seconds.
    LANGUAGE_UNAVAILABLE = (
        "Selected language hasn't been transcribed. Check `available_languages`."
    )

    def __init__(self, api_key: str):
        self._api_key = api_key.strip()

    def _search(self, engine: str, video_id: str, **params: str) -> Dict[str, Any]:
        if not self._api_key:
            raise SearchApiError("SearchApi is not configured")
        try:
            response = requests.get(
                self.URL,
                params={"engine": engine, "video_id": video_id, **params},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self.TIMEOUT,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise SearchApiError("SearchApi request timed out") from None
        except requests.RequestException:
            raise SearchApiError("SearchApi request failed") from None

        try:
            # Do not follow redirects with credentials, retry billable requests, or
            # expose response text / HTTP exceptions (which may contain secrets).
            if not 200 <= response.status_code < 300:
                raise SearchApiError("SearchApi returned an unsuccessful HTTP status")
            try:
                payload = response.json()
            except ValueError:
                raise SearchApiError("SearchApi returned invalid JSON") from None
        finally:
            response.close()

        if not isinstance(payload, dict):
            raise SearchApiError("SearchApi returned an invalid response")
        return payload

    @staticmethod
    def _check_error(payload: Dict[str, Any]) -> None:
        metadata = payload.get("search_metadata")
        if payload.get("error") or (
            isinstance(metadata, dict)
            and metadata.get("status") not in (None, "Success")
        ):
            raise SearchApiError("SearchApi could not retrieve the requested content")

    @staticmethod
    def _text(value: Any, default: Optional[str] = None) -> Optional[str]:
        return value if isinstance(value, str) and value.strip() else default

    @staticmethod
    def _count(value: Any, default: Optional[int] = None) -> Optional[int]:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default

    @staticmethod
    def _upload_date(value: Any) -> Optional[str]:
        if isinstance(value, str):
            for date_format in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%Y%m%d"):
                try:
                    return datetime.strptime(value, date_format).strftime("%Y%m%d")
                except ValueError:
                    pass
        return None

    def get_video_info(self, video_id: str, url: str) -> Dict[str, Any]:
        payload = self._search("youtube_video", video_id)
        self._check_error(payload)
        video = payload.get("video")
        if not isinstance(video, dict) or not self._text(video.get("title")):
            raise SearchApiError("SearchApi returned no usable video metadata")
        channel = payload.get("channel")
        channel_name = channel.get("name") if isinstance(channel, dict) else None
        return {
            "title": video["title"],
            "description": self._text(video.get("description"), ""),
            "duration": self._count(video.get("length_seconds"), 0),
            "view_count": self._count(video.get("views")),
            "channel": self._text(video.get("author"), self._text(channel_name, "Unknown Channel")),
            "upload_date": self._upload_date(video.get("published_time")),
            "url": url,
            "video_id": video_id,
            "thumbnail_url": self._text(
                video.get("thumbnail"),
                f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            ),
        }

    def get_transcript(
        self, video_id: str, language: str, max_length: int
    ) -> Tuple[str, str]:
        payload = self._search("youtube_transcripts", video_id, lang=language)

        # The existing provider falls back to another available language. Select
        # one explicitly so detected_transcript_language is never guessed from
        # the requested language when SearchApi substitutes a different track.
        if payload.get("error") == self.LANGUAGE_UNAVAILABLE:
            available = payload.get("available_languages")
            if isinstance(available, list):
                for entry in available:
                    candidate = entry.get("lang") if isinstance(entry, dict) else None
                    if isinstance(candidate, str) and candidate.strip() and candidate != language:
                        language = candidate
                        payload = self._search("youtube_transcripts", video_id, lang=language)
                        break

        self._check_error(payload)
        segments = payload.get("transcripts")
        if not isinstance(segments, list) or not segments:
            raise SearchApiError("SearchApi returned no usable transcript")

        lines = []
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                raise SearchApiError("SearchApi returned an invalid transcript")
            if segment["text"].strip():
                lines.append(segment["text"])
        if not lines:
            raise SearchApiError("SearchApi returned no usable transcript")

        text = "\n".join(lines)
        if max_length and len(text) > max_length:
            text = text[:max_length] + "\n[Transcript truncated...]"
        return text, language
