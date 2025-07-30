"""Schema definitions for YouTube video processing."""

import re
from typing import Optional
from pydantic import BaseModel, validator


class VideoQuery(BaseModel):
    """Schema for YouTube video query parameters."""
    
    url: str
    max_transcript_length: int = 10000
    include_comments: bool = False
    language: str = "en"
    
    @validator("url")
    def validate_youtube_url(cls, v):
        """Validate that the URL is a valid YouTube URL."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, v):
                return v
        
        raise ValueError("Invalid YouTube URL format")
    
    @validator("max_transcript_length")
    def validate_transcript_length(cls, v):
        """Validate transcript length is reasonable."""
        if v < 100:
            raise ValueError("Transcript length must be at least 100 characters")
        if v > 100000:
            raise ValueError("Transcript length cannot exceed 100,000 characters")
        return v
    
    def extract_video_id(self) -> str:
        """Extract video ID from YouTube URL."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, self.url)
            if match:
                return match.group(1)
        
        raise ValueError("Could not extract video ID from URL")


class VideoInfo(BaseModel):
    """Schema for YouTube video information."""
    
    title: str
    description: Optional[str] = None
    duration: int  # in seconds
    view_count: Optional[int] = None
    channel: Optional[str] = None
    upload_date: Optional[str] = None
    url: str
    video_id: str
    thumbnail_url: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        extra = "allow" 