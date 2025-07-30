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
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        print("DEBUG: Checking YouTube processor dependencies...")
        
        if YouTubeTranscriptApi is None:
            print("ERROR: youtube-transcript-api not imported - transcript extraction will fail")
        else:
            print("SUCCESS: youtube-transcript-api imported successfully")
        
        if TextFormatter is None:
            print("ERROR: TextFormatter not imported - transcript formatting will fail")
        else:
            print("SUCCESS: TextFormatter imported successfully")
        
        if yt_dlp is None:
            print("WARNING: yt-dlp not imported - will fallback to pytube")
        else:
            print("SUCCESS: yt-dlp imported successfully")
        
        if YouTube is None:
            print("WARNING: pytube not imported - video info extraction limited")
        else:
            print("SUCCESS: pytube imported successfully")
    
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
        print(f"DEBUG: Attempting transcript extraction for video_id: {video_id}")
        print(f"DEBUG: Language: {language}, Max length: {max_length}")
        
        if not YouTubeTranscriptApi:
            print("ERROR: YouTubeTranscriptApi is not available - package not imported")
            return None
        
        if not self.text_formatter:
            print("ERROR: TextFormatter is not available - package not imported")
            return None
        
        def extract_transcript():
            try:
                print(f"DEBUG: Creating YouTubeTranscriptApi instance...")
                
                # Create an instance of YouTubeTranscriptApi (correct usage pattern)
                ytt_api = YouTubeTranscriptApi()
                print(f"DEBUG: Available methods on ytt_api instance: {[method for method in dir(ytt_api) if not method.startswith('_')]}")
                
                # Try the direct fetch method first (current API)
                try:
                    print(f"DEBUG: Attempting fetch for video {video_id} with language {language}")
                    fetched_transcript = ytt_api.fetch(video_id, languages=[language])
                    print(f"DEBUG: Successfully fetched transcript object: {type(fetched_transcript)}")
                    
                    # Use the FetchedTranscript object directly for formatting
                    print(f"DEBUG: Retrieved {len(fetched_transcript)} transcript segments")
                    
                    print("DEBUG: Formatting transcript...")
                    formatted_text = self.text_formatter.format_transcript(fetched_transcript)
                    print(f"DEBUG: Formatted transcript length: {len(formatted_text)} characters")
                    
                    # Trim to max length if specified
                    if max_length and len(formatted_text) > max_length:
                        formatted_text = formatted_text[:max_length] + "\n[Transcript truncated...]"
                        print(f"DEBUG: Truncated transcript to {max_length} characters")
                    
                    print("DEBUG: Transcript extraction completed successfully")
                    return formatted_text
                    
                except Exception as e:
                    print(f"DEBUG: Direct fetch failed: {e}")
                    
                    # Fallback to listing transcripts and manually selecting
                    try:
                        print(f"DEBUG: Trying list method for video {video_id}")
                        transcript_list = ytt_api.list(video_id)
                        print(f"DEBUG: Retrieved transcript list: {type(transcript_list)}")
                        
                        print(f"DEBUG: Available transcripts: {[t.language_code for t in transcript_list]}")
                        
                        # Try manual captions first, then auto-generated
                        transcript = None
                        try:
                            print(f"DEBUG: Attempting to find manually created transcript in {language}")
                            transcript = transcript_list.find_manually_created_transcript([language])
                            print(f"DEBUG: Found manually created transcript in {language}")
                        except Exception as e:
                            print(f"DEBUG: Manual transcript not found: {e}")
                            try:
                                print(f"DEBUG: Attempting to find auto-generated transcript in {language}")
                                transcript = transcript_list.find_generated_transcript([language])
                                print(f"DEBUG: Found auto-generated transcript in {language}")
                            except Exception as e2:
                                print(f"DEBUG: Auto-generated transcript not found: {e2}")
                                # Fall back to any available transcript
                                try:
                                    print("DEBUG: Falling back to any available English transcript")
                                    transcript = transcript_list.find_transcript(['en'])
                                    print("DEBUG: Found fallback English transcript")
                                except Exception as e3:
                                    print(f"DEBUG: No transcript found at all: {e3}")
                                    raise e3
                        
                        if not transcript:
                            print("ERROR: No transcript object found")
                            return None
                        
                        # Fetch and format transcript
                        print("DEBUG: Fetching transcript data...")
                        fetched_transcript = transcript.fetch()
                        print(f"DEBUG: Retrieved {len(fetched_transcript)} transcript segments")
                        
                        print("DEBUG: Formatting transcript...")
                        formatted_text = self.text_formatter.format_transcript(fetched_transcript)
                        print(f"DEBUG: Formatted transcript length: {len(formatted_text)} characters")
                        
                        # Trim to max length if specified
                        if max_length and len(formatted_text) > max_length:
                            formatted_text = formatted_text[:max_length] + "\n[Transcript truncated...]"
                            print(f"DEBUG: Truncated transcript to {max_length} characters")
                        
                        print("DEBUG: Transcript extraction completed successfully")
                        return formatted_text
                        
                    except Exception as e2:
                        print(f"DEBUG: List method also failed: {e2}")
                        raise e2
                
            except Exception as e:
                print(f"ERROR: Transcript extraction failed: {e}")
                print(f"ERROR: Exception type: {type(e).__name__}")
                import traceback
                print(f"ERROR: Full traceback:\n{traceback.format_exc()}")
                return None
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, extract_transcript)
        
        if result is None:
            print("WARNING: Transcript extraction returned None")
        else:
            print(f"SUCCESS: Transcript extraction returned {len(result)} characters")
        
        return result
    
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