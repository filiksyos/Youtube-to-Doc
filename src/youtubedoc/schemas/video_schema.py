"""Schema definitions for YouTube video processing."""

from typing import Optional
from pydantic import BaseModel, validator

from ..utils.youtube_url_validator import YouTubeURLValidator


class VideoQuery(BaseModel):
    """Schema for YouTube video query parameters."""
    
    url: str
    max_transcript_length: int = 10000
    include_comments: bool = False
    language: str = "en"
    
    @validator("url")
    def validate_youtube_url(cls, v):
        """Validate that the URL is a valid YouTube URL."""
        if not YouTubeURLValidator.is_valid_youtube_url(v):
            raise ValueError("Invalid YouTube URL format")
        return v
    
    @validator("max_transcript_length")
    def validate_transcript_length(cls, v):
        """Validate transcript length is reasonable."""
        if v < 100:
            raise ValueError("Transcript length must be at least 100 characters")
        return v
    
    def extract_video_id(self) -> str:
        """Extract video ID from YouTube URL."""
        video_id = YouTubeURLValidator.extract_video_id(self.url)
        if video_id:
            return video_id
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