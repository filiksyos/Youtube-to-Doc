"""YouTube video processor for extracting video data, transcripts, and comments."""

import asyncio
import os
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
except ImportError:
    YouTubeTranscriptApi = None
    TextFormatter = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from pytube import YouTube
    from pytube.exceptions import VideoUnavailable, RegexMatchError
except ImportError:
    YouTube = None
    VideoUnavailable = None
    RegexMatchError = None

from .schemas.video_schema import VideoQuery, VideoInfo


class YoutubeProcessor:
    """Processor for extracting YouTube video information and content."""
    
    def __init__(self):
        """Initialize the YouTube processor."""
        self.text_formatter = TextFormatter() if TextFormatter else None
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    
    async def process_video(
        self, 
        query: VideoQuery
    ) -> Tuple[Dict[str, Any], Optional[str], Optional[List[str]]]:
        """
        Process a YouTube video and extract information, transcript, and comments.
        
        Parameters
        ----------
        query : VideoQuery
            The video query parameters.
            
        Returns
        -------
        Tuple[Dict[str, Any], Optional[str], Optional[List[str]]]
            A tuple containing video info, transcript, and comments.
        """
        video_id = query.extract_video_id()
        
        # Extract video information
        video_info = await self._get_video_info(video_id, query.url)
        
        # Extract transcript
        transcript = await self._get_transcript(video_id, query.language, query.max_transcript_length)
        
        # Extract comments if requested
        comments = None
        if query.include_comments:
            comments = await self._get_comments(video_id)
        
        return video_info, transcript, comments
    
    async def _get_video_info(self, video_id: str, url: str) -> Dict[str, Any]:
        """
        Extract video information using available libraries.
        
        Parameters
        ----------
        video_id : str
            The YouTube video ID.
        url : str
            The full YouTube URL.
            
        Returns
        -------
        Dict[str, Any]
            Video information dictionary.
        """
        # Try yt-dlp first (most reliable)
        if yt_dlp:
            try:
                return await self._get_video_info_yt_dlp(video_id, url)
            except Exception as e:
                print(f"yt-dlp failed: {e}")
        
        # Fallback to pytube
        if YouTube:
            try:
                return await self._get_video_info_pytube(url)
            except Exception as e:
                print(f"pytube failed: {e}")
        
        # Last resort - return minimal info
        return {
            "title": f"Video {video_id}",
            "description": "Description not available",
            "duration": 0,
            "view_count": None,
            "channel": "Unknown Channel",
            "upload_date": None,
            "url": url,
            "video_id": video_id,
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        }
    
    async def _get_video_info_yt_dlp(self, video_id: str, url: str) -> Dict[str, Any]:
        """Extract video info using yt-dlp."""
        def extract_info():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get('title', 'Unknown Title'),
                    "description": info.get('description', ''),
                    "duration": info.get('duration', 0),
                    "view_count": info.get('view_count'),
                    "channel": info.get('uploader', 'Unknown Channel'),
                    "upload_date": info.get('upload_date'),
                    "url": url,
                    "video_id": video_id,
                    "thumbnail_url": info.get('thumbnail')
                }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract_info)
    
    async def _get_video_info_pytube(self, url: str) -> Dict[str, Any]:
        """Extract video info using pytube."""
        def extract_info():
            yt = YouTube(url)
            return {
                "title": yt.title,
                "description": yt.description,
                "duration": yt.length,
                "view_count": yt.views,
                "channel": yt.author,
                "upload_date": yt.publish_date.strftime('%Y%m%d') if yt.publish_date else None,
                "url": url,
                "video_id": yt.video_id,
                "thumbnail_url": yt.thumbnail_url
            }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract_info)
    
    async def _get_transcript(
        self, 
        video_id: str, 
        language: str = "en", 
        max_length: int = 10000
    ) -> Optional[str]:
        """
        Extract video transcript using YouTube Transcript API.
        
        Parameters
        ----------
        video_id : str
            The YouTube video ID.
        language : str
            Preferred language for transcript.
        max_length : int
            Maximum transcript length.
            
        Returns
        -------
        Optional[str]
            The transcript text or None if not available.
        """
        if not YouTubeTranscriptApi:
            return None
        
        def extract_transcript():
            try:
                # Try to get transcript in specified language
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Try manual captions first, then auto-generated
                try:
                    transcript = transcript_list.find_manually_created_transcript([language])
                except:
                    try:
                        transcript = transcript_list.find_generated_transcript([language])
                    except:
                        # Fall back to any available transcript
                        transcript = transcript_list.find_transcript(['en'])
                
                # Fetch and format transcript
                transcript_data = transcript.fetch()
                formatted_text = self.text_formatter.format_transcript(transcript_data) if self.text_formatter else ""
                
                # Trim to max length if specified
                if max_length and len(formatted_text) > max_length:
                    formatted_text = formatted_text[:max_length] + "\n[Transcript truncated...]"
                
                return formatted_text
                
            except Exception as e:
                print(f"Transcript extraction failed: {e}")
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract_transcript)
    
    async def _get_comments(self, video_id: str, max_comments: int = 20) -> Optional[List[str]]:
        """
        Extract video comments (limited implementation).
        
        Parameters
        ----------
        video_id : str
            The YouTube video ID.
        max_comments : int
            Maximum number of comments to extract.
            
        Returns
        -------
        Optional[List[str]]
            List of comment texts or None if not available.
        """
        # Note: YouTube Comments API requires API key and has quotas
        # This is a placeholder implementation
        # In a production environment, you would use YouTube Data API v3
        
        if self.youtube_api_key:
            # TODO: Implement YouTube Data API v3 comments extraction
            # For now, return placeholder comments
            return [
                "Great video! Very informative.",
                "Thanks for sharing this content.",
                "This helped me understand the topic better."
            ]
        
        return None 