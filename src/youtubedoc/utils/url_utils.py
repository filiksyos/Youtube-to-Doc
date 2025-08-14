"""URL utilities for YouTube video processing.

DEPRECATED: This module is now deprecated. Use youtube_url_validator.py instead.
These functions are kept for backward compatibility but delegate to the
centralized YouTubeURLValidator class.
"""

from typing import Optional
from .youtube_url_validator import YouTubeURLValidator


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from various YouTube URL formats.
    
    DEPRECATED: Use YouTubeURLValidator.extract_video_id() instead.
    
    Parameters
    ----------
    url : str
        The YouTube URL.
        
    Returns
    -------
    Optional[str]
        The video ID if found, None otherwise.
    """
    return YouTubeURLValidator.extract_video_id(url)


def is_valid_youtube_url(url: str) -> bool:
    """
    Check if a URL is a valid YouTube URL.
    
    DEPRECATED: Use YouTubeURLValidator.is_valid_youtube_url() instead.
    
    Parameters
    ----------
    url : str
        The URL to validate.
        
    Returns
    -------
    bool
        True if valid YouTube URL, False otherwise.
    """
    return YouTubeURLValidator.is_valid_youtube_url(url)


def normalize_youtube_url(url: str) -> Optional[str]:
    """
    Normalize a YouTube URL to standard format.
    
    DEPRECATED: Use YouTubeURLValidator.normalize_youtube_url() instead.
    
    Parameters
    ----------
    url : str
        The YouTube URL to normalize.
        
    Returns
    -------
    Optional[str]
        Normalized YouTube URL or None if invalid.
    """
    return YouTubeURLValidator.normalize_youtube_url(url) 