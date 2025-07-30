"""URL utilities for YouTube video processing."""

import re
from typing import Optional


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from various YouTube URL formats.
    
    Parameters
    ----------
    url : str
        The YouTube URL.
        
    Returns
    -------
    Optional[str]
        The video ID if found, None otherwise.
    """
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def is_valid_youtube_url(url: str) -> bool:
    """
    Check if a URL is a valid YouTube URL.
    
    Parameters
    ----------
    url : str
        The URL to validate.
        
    Returns
    -------
    bool
        True if valid YouTube URL, False otherwise.
    """
    return extract_video_id(url) is not None


def normalize_youtube_url(url: str) -> Optional[str]:
    """
    Normalize a YouTube URL to standard format.
    
    Parameters
    ----------
    url : str
        The YouTube URL to normalize.
        
    Returns
    -------
    Optional[str]
        Normalized YouTube URL or None if invalid.
    """
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return None 