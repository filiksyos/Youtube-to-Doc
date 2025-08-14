"""Centralized YouTube URL validation and processing utilities.

This module provides a single source of truth for YouTube URL validation,
video ID extraction, and URL normalization to eliminate code duplication
across the application.
"""

import re
from typing import Optional, List, Tuple
from urllib.parse import urlparse, parse_qs


class YouTubeURLValidator:
    """Centralized validator for YouTube URLs with comprehensive pattern support."""
    
    # Comprehensive list of YouTube URL patterns covering all common formats
    URL_PATTERNS: List[str] = [
        # Standard watch URLs
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        # Shortened URLs
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        # Embed URLs
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        # Direct video URLs
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        # Mobile URLs
        r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    ]
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.
        
        This method uses both regex patterns and URL parsing to handle
        all common YouTube URL formats reliably.
        
        Parameters
        ----------
        url : str
            The YouTube URL to extract video ID from.
            
        Returns
        -------
        Optional[str]
            The 11-character video ID if found, None otherwise.
        """
        if not url or not isinstance(url, str):
            return None
        
        # First try regex patterns for comprehensive format support
        for pattern in cls.URL_PATTERNS:
            match = re.search(pattern, url.strip())
            if match:
                video_id = match.group(1)
                if cls._is_valid_video_id(video_id):
                    return video_id
        
        # Fallback to URL parsing for edge cases
        try:
            parsed = urlparse(url.strip())
            
            # Handle standard youtube.com/watch URLs
            if parsed.netloc.endswith("youtube.com") and parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [None])[0]
                if video_id and cls._is_valid_video_id(video_id):
                    return video_id
            
            # Handle youtu.be URLs
            elif parsed.netloc == "youtu.be" and parsed.path:
                video_id = parsed.path.lstrip("/").split("?")[0]  # Remove query params
                if cls._is_valid_video_id(video_id):
                    return video_id
                    
        except Exception:
            pass
        
        return None
    
    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        """
        Check if a URL is a valid YouTube URL.
        
        Parameters
        ----------
        url : str
            The URL to validate.
            
        Returns
        -------
        bool
            True if valid YouTube URL with extractable video ID, False otherwise.
        """
        return cls.extract_video_id(url) is not None
    
    @classmethod
    def normalize_youtube_url(cls, url: str) -> Optional[str]:
        """
        Normalize a YouTube URL to standard format.
        
        Parameters
        ----------
        url : str
            The YouTube URL to normalize.
            
        Returns
        -------
        Optional[str]
            Normalized YouTube URL (https://www.youtube.com/watch?v=VIDEO_ID) 
            or None if invalid.
        """
        video_id = cls.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
    
    @classmethod
    def validate_and_extract(cls, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate URL and extract video ID in one operation.
        
        This is an efficient method that combines validation and extraction
        to avoid duplicate processing.
        
        Parameters
        ----------
        url : str
            The YouTube URL to validate and extract from.
            
        Returns
        -------
        Tuple[bool, Optional[str], Optional[str]]
            A tuple containing (is_valid, video_id, normalized_url).
        """
        video_id = cls.extract_video_id(url)
        if video_id:
            normalized_url = f"https://www.youtube.com/watch?v={video_id}"
            return True, video_id, normalized_url
        return False, None, None
    
    @staticmethod
    def _is_valid_video_id(video_id: str) -> bool:
        """
        Validate that a string is a valid YouTube video ID.
        
        Parameters
        ----------
        video_id : str
            The video ID to validate.
            
        Returns
        -------
        bool
            True if valid video ID format, False otherwise.
        """
        if not video_id or not isinstance(video_id, str):
            return False
        
        # YouTube video IDs are exactly 11 characters and contain only
        # alphanumeric characters, hyphens, and underscores
        return (
            len(video_id) == 11 and
            re.match(r'^[a-zA-Z0-9_-]{11}$', video_id) is not None
        )


# Convenience functions for backward compatibility
def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL. Convenience wrapper around YouTubeURLValidator."""
    return YouTubeURLValidator.extract_video_id(url)


def is_valid_youtube_url(url: str) -> bool:
    """Check if URL is valid YouTube URL. Convenience wrapper around YouTubeURLValidator."""
    return YouTubeURLValidator.is_valid_youtube_url(url)


def normalize_youtube_url(url: str) -> Optional[str]:
    """Normalize YouTube URL. Convenience wrapper around YouTubeURLValidator."""
    return YouTubeURLValidator.normalize_youtube_url(url)