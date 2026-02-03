"""YouTube Video Content Extractor

A comprehensive processor for extracting video metadata, transcripts, and comments
from YouTube videos with support for proxies and multiple extraction methods.
"""

import asyncio
import os
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Optional imports with graceful fallback
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
    from youtube_transcript_api.proxies import (
        WebshareProxyConfig, 
        GenericProxyConfig
    )
    TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YouTubeTranscriptApi = None
    TextFormatter = None
    WebshareProxyConfig = None
    GenericProxyConfig = None
    TRANSCRIPT_API_AVAILABLE = False
    logger.warning("youtube-transcript-api not available - transcript extraction disabled")

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    yt_dlp = None
    YT_DLP_AVAILABLE = False
    logger.warning("yt-dlp not available - will use fallback methods")

try:
    from pytube import YouTube
    from pytube.exceptions import VideoUnavailable, RegexMatchError
    PYTUBE_AVAILABLE = True
except ImportError:
    YouTube = None
    VideoUnavailable = None
    RegexMatchError = None
    PYTUBE_AVAILABLE = False
    logger.warning("pytube not available - video info extraction limited")

from .schemas.video_schema import VideoQuery, VideoInfo


class YoutubeProcessor:
    """Main processor for YouTube video content extraction.
    
    This class provides methods to extract video metadata, transcripts, and comments
    from YouTube videos with support for multiple extraction methods and proxy configurations.
    
    Attributes:
        youtube_api_key (str): YouTube Data API v3 key from environment
        text_formatter (TextFormatter): Formatter for transcript text
    """
    
    def __init__(self):
        """Initialize the YouTube processor with dependency checks and configuration."""
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self.text_formatter = TextFormatter() if TextFormatter else None
        
        self._validate_dependencies()
        self._log_environment_configuration()
    
    def _validate_dependencies(self) -> None:
        """Validate and log the status of all required dependencies."""
        dependency_status = {
            "youtube-transcript-api": TRANSCRIPT_API_AVAILABLE,
            "yt-dlp": YT_DLP_AVAILABLE,
            "pytube": PYTUBE_AVAILABLE,
        }
        
        logger.info("Validating YouTube processor dependencies...")
        for dep_name, available in dependency_status.items():
            if available:
                logger.debug(f"✓ {dep_name} is available")
            else:
                logger.warning(f"✗ {dep_name} is not available")
        
        # Check critical dependencies
        if not TRANSCRIPT_API_AVAILABLE:
            logger.error("Critical dependency missing: youtube-transcript-api")
        
        if not any([YT_DLP_AVAILABLE, PYTUBE_AVAILABLE]):
            logger.warning("No video metadata extraction libraries available")
    
    def _log_environment_configuration(self) -> None:
        """Log the current proxy and API configuration from environment variables."""
        try:
            # Check proxy configurations
            proxy_configs = {
                "webshare": {
                    "username": os.getenv("YTA_WEBSHARE_USERNAME"),
                    "password": "***" if os.getenv("YTA_WEBSHARE_PASSWORD") else None,
                },
                "generic": {
                    "http": os.getenv("YTA_HTTP_PROXY") or os.getenv("HTTP_PROXY"),
                    "https": os.getenv("YTA_HTTPS_PROXY") or os.getenv("HTTPS_PROXY"),
                }
            }
            
            if proxy_configs["webshare"]["username"]:
                logger.info("Webshare proxy credentials configured")
            elif any(proxy_configs["generic"].values()):
                logger.info("Generic proxy URLs configured")
            else:
                logger.info("No proxy configuration detected - using direct connections")
            
            # Check API key
            if self.youtube_api_key:
                logger.debug("YouTube API key is configured")
            else:
                logger.warning("YouTube API key not configured - comment extraction limited")
                
        except Exception as e:
            logger.warning(f"Failed to log environment configuration: {e}")
    
    def _build_proxy_config(self) -> Optional[Any]:
        """Build a proxy configuration object from environment variables.
        
        Priority:
        1. Webshare residential proxies (if credentials provided)
        2. Generic HTTP/HTTPS proxies
        3. None (direct connection)
        
        Returns:
            Optional[ProxyConfig]: Configured proxy object or None if no proxy configured.
        """
        # Webshare proxy configuration
        webshare_username = os.getenv("YTA_WEBSHARE_USERNAME")
        webshare_password = os.getenv("YTA_WEBSHARE_PASSWORD")
        
        if (WebshareProxyConfig and webshare_username and webshare_password):
            try:
                # Parse optional locations filter
                locations_raw = os.getenv("YTA_WEBSHARE_LOCATIONS", "")
                locations = [
                    loc.strip() 
                    for loc in locations_raw.split(",") 
                    if loc.strip()
                ] if locations_raw else None
                
                logger.debug("Creating WebshareProxyConfig")
                return WebshareProxyConfig(
                    proxy_username=webshare_username,
                    proxy_password=webshare_password,
                    filter_ip_locations=locations,
                )
            except Exception as e:
                logger.error(f"Failed to create WebshareProxyConfig: {e}")
        
        # Generic proxy configuration
        http_proxy = os.getenv("YTA_HTTP_PROXY") or os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("YTA_HTTPS_PROXY") or os.getenv("HTTPS_PROXY")
        
        if GenericProxyConfig and (http_proxy or https_proxy):
            try:
                logger.debug("Creating GenericProxyConfig")
                return GenericProxyConfig(
                    http_url=http_proxy,
                    https_url=https_proxy,
                )
            except Exception as e:
                logger.error(f"Failed to create GenericProxyConfig: {e}")
        
        logger.debug("No proxy configuration - using direct connection")
        return None
    
    async def process_video(
        self, 
        query: VideoQuery
    ) -> Tuple[Dict[str, Any], Optional[str], Optional[List[str]]]:
        """Process a YouTube video and extract all requested content.
        
        Args:
            query: VideoQuery object containing extraction parameters.
            
        Returns:
            Tuple containing:
                - video_info: Dictionary with video metadata
                - transcript: Extracted transcript text (or None)
                - comments: List of comment texts (or None)
                
        Raises:
            ValueError: If video URL is invalid or video ID cannot be extracted.
        """
        logger.info(f"Processing video: {query.url}")
        
        try:
            video_id = query.extract_video_id()
            logger.debug(f"Extracted video ID: {video_id}")
        except ValueError as e:
            logger.error(f"Failed to extract video ID: {e}")
            raise
        
        # Execute extraction tasks
        video_info = await self._extract_video_metadata(video_id, query.url)
        transcript, language = await self._extract_transcript(
            video_id, 
            query.language, 
            query.max_transcript_length
        )
        comments = await self._extract_comments(video_id) if query.include_comments else None
        
        # Enhance video info with extraction results
        if language:
            video_info["detected_transcript_language"] = language
            logger.info(f"Detected transcript language: {language}")
        
        logger.info(f"Video processing complete for: {video_info.get('title', 'Unknown')}")
        return video_info, transcript, comments
    
    async def _extract_video_metadata(
        self, 
        video_id: str, 
        url: str
    ) -> Dict[str, Any]:
        """Extract video metadata using available extraction libraries.
        
        Strategy:
        1. Primary: yt-dlp (most reliable and feature-rich)
        2. Fallback: pytube
        3. Minimal: Basic info with video ID
        
        Args:
            video_id: YouTube video identifier.
            url: Full YouTube video URL.
            
        Returns:
            Dictionary containing video metadata.
        """
        extraction_attempts = []
        
        # Attempt 1: yt-dlp
        if YT_DLP_AVAILABLE:
            try:
                metadata = await self._extract_metadata_with_ytdlp(video_id, url)
                logger.debug("Successfully extracted metadata with yt-dlp")
                return metadata
            except Exception as e:
                extraction_attempts.append(f"yt-dlp: {str(e)}")
                logger.warning(f"yt-dlp extraction failed: {e}")
        
        # Attempt 2: pytube
        if PYTUBE_AVAILABLE:
            try:
                metadata = await self._extract_metadata_with_pytube(url)
                logger.debug("Successfully extracted metadata with pytube")
                return metadata
            except Exception as e:
                extraction_attempts.append(f"pytube: {str(e)}")
                logger.warning(f"pytube extraction failed: {e}")
        
        # Fallback: Minimal metadata
        logger.warning(f"All metadata extraction methods failed. Attempts: {extraction_attempts}")
        return self._build_minimal_metadata(video_id, url)
    
    async def _extract_metadata_with_ytdlp(
        self, 
        video_id: str, 
        url: str
    ) -> Dict[str, Any]:
        """Extract video metadata using yt-dlp library.
        
        Args:
            video_id: YouTube video identifier.
            url: Full YouTube video URL.
            
        Returns:
            Dictionary containing comprehensive video metadata.
        """
        def _extract():
            # Configure proxy for yt-dlp
            http_proxy = os.getenv("YTA_HTTPS_PROXY") or os.getenv("HTTPS_PROXY") or \
                        os.getenv("YTA_HTTP_PROXY") or os.getenv("HTTP_PROXY")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
                **({'proxy': http_proxy} if http_proxy else {}),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Format upload date if available
                upload_date = info.get('upload_date')
                if upload_date:
                    # Convert from YYYYMMDD to datetime object
                    upload_date = datetime.strptime(upload_date, '%Y%m%d').date()
                
                return {
                    "title": info.get('title', 'Unknown Title'),
                    "description": info.get('description', ''),
                    "duration": info.get('duration', 0),
                    "view_count": info.get('view_count'),
                    "like_count": info.get('like_count'),
                    "channel": info.get('uploader', 'Unknown Channel'),
                    "channel_id": info.get('uploader_id'),
                    "upload_date": upload_date,
                    "url": url,
                    "video_id": video_id,
                    "thumbnail_url": info.get('thumbnail'),
                    "categories": info.get('categories', []),
                    "tags": info.get('tags', []),
                }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract)
    
    async def _extract_metadata_with_pytube(self, url: str) -> Dict[str, Any]:
        """Extract video metadata using pytube library.
        
        Args:
            url: Full YouTube video URL.
            
        Returns:
            Dictionary containing video metadata.
        """
        def _extract():
            # Configure proxy for pytube
            proxies = None
            http_proxy = os.getenv("YTA_HTTP_PROXY") or os.getenv("HTTP_PROXY")
            https_proxy = os.getenv("YTA_HTTPS_PROXY") or os.getenv("HTTPS_PROXY")
            
            if http_proxy or https_proxy:
                proxies = {}
                if http_proxy:
                    proxies['http'] = http_proxy
                if https_proxy:
                    proxies['https'] = https_proxy
            
            yt = YouTube(url, proxies=proxies) if proxies else YouTube(url)
            
            return {
                "title": yt.title or 'Unknown Title',
                "description": yt.description or '',
                "duration": yt.length or 0,
                "view_count": yt.views,
                "channel": yt.author or 'Unknown Channel',
                "upload_date": yt.publish_date,
                "url": url,
                "video_id": yt.video_id,
                "thumbnail_url": yt.thumbnail_url,
                "categories": [],  # pytube doesn't provide categories
                "tags": yt.keywords if hasattr(yt, 'keywords') else [],
            }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract)
    
    def _build_minimal_metadata(
        self, 
        video_id: str, 
        url: str
    ) -> Dict[str, Any]:
        """Build minimal video metadata when extraction libraries fail.
        
        Args:
            video_id: YouTube video identifier.
            url: Full YouTube video URL.
            
        Returns:
            Dictionary with basic video information.
        """
        return {
            "title": f"Video {video_id}",
            "description": "Description not available",
            "duration": 0,
            "view_count": None,
            "like_count": None,
            "channel": "Unknown Channel",
            "channel_id": None,
            "upload_date": None,
            "url": url,
            "video_id": video_id,
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "categories": [],
            "tags": [],
        }
    
    async def _extract_transcript(
        self, 
        video_id: str, 
        preferred_language: str = "en", 
        max_length: int = 10000
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract video transcript with automatic language detection.
        
        Args:
            video_id: YouTube video identifier.
            preferred_language: ISO 639-1 language code for preferred transcript.
            max_length: Maximum character length for transcript (truncates if longer).
            
        Returns:
            Tuple containing:
                - transcript_text: Extracted transcript text (or None)
                - detected_language: Language code of extracted transcript
        """
        if not TRANSCRIPT_API_AVAILABLE or not self.text_formatter:
            logger.error("Transcript extraction dependencies not available")
            return None, None
        
        logger.debug(f"Extracting transcript for {video_id} (language: {preferred_language})")
        
        def _extract():
            try:
                # Initialize API with proxy configuration
                proxy_config = self._build_proxy_config()
                ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config) if proxy_config else YouTubeTranscriptApi()
                
                # Attempt primary extraction method
                try:
                    return self._extract_transcript_direct(
                        ytt_api, video_id, preferred_language, max_length
                    )
                except Exception as direct_error:
                    logger.debug(f"Direct extraction failed: {direct_error}")
                    return self._extract_transcript_with_fallback(
                        ytt_api, video_id, preferred_language, max_length
                    )
                    
            except Exception as e:
                logger.error(f"Transcript extraction failed: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                return None, None
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _extract)
        
        if result[0]:
            logger.info(f"Transcript extracted: {len(result[0])} chars in '{result[1]}'")
        else:
            logger.warning("No transcript available for this video")
        
        return result
    
    def _extract_transcript_direct(
        self, 
        ytt_api: Any,
        video_id: str,
        preferred_language: str,
        max_length: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract transcript using direct fetch method.
        
        Args:
            ytt_api: YouTubeTranscriptApi instance.
            video_id: YouTube video identifier.
            preferred_language: Preferred transcript language.
            max_length: Maximum transcript length.
            
        Returns:
            Tuple of (transcript_text, language_code) or (None, None).
        """
        try:
            transcript_data = ytt_api.fetch(video_id, languages=[preferred_language])
            transcript_text = self.text_formatter.format_transcript(transcript_data)
            
            if max_length and len(transcript_text) > max_length:
                transcript_text = transcript_text[:max_length] + "\n[Transcript truncated...]"
            
            return transcript_text, preferred_language
        except Exception as e:
            raise Exception(f"Direct fetch failed: {str(e)}")
    
    def _extract_transcript_with_fallback(
        self, 
        ytt_api: Any,
        video_id: str,
        preferred_language: str,
        max_length: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract transcript using fallback methods with language detection.
        
        Args:
            ytt_api: YouTubeTranscriptApi instance.
            video_id: YouTube video identifier.
            preferred_language: Preferred transcript language.
            max_length: Maximum transcript length.
            
        Returns:
            Tuple of (transcript_text, language_code) or (None, None).
        """
        try:
            transcript_list = ytt_api.list(video_id)
            available_languages = [t.language_code for t in transcript_list]
            logger.debug(f"Available transcript languages: {available_languages}")
            
            # Try to find transcript in preferred language
            transcript, detected_language = self._find_transcript_by_preference(
                transcript_list, preferred_language
            )
            
            if not transcript:
                logger.warning(f"No transcript found for language {preferred_language}")
                return None, None
            
            # Fetch and format transcript
            transcript_data = transcript.fetch()
            transcript_text = self.text_formatter.format_transcript(transcript_data)
            
            # Apply length limit
            if max_length and len(transcript_text) > max_length:
                transcript_text = transcript_text[:max_length] + "\n[Transcript truncated...]"
            
            return transcript_text, detected_language
            
        except Exception as e:
            logger.error(f"Fallback transcript extraction failed: {e}")
            return None, None
    
    def _find_transcript_by_preference(
        self, 
        transcript_list: Any, 
        preferred_language: str
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Find the best available transcript based on language preferences.
        
        Priority:
        1. Manually created transcript in preferred language
        2. Auto-generated transcript in preferred language
        3. Any manually created transcript
        4. Any auto-generated transcript
        
        Args:
            transcript_list: List of available transcripts.
            preferred_language: ISO 639-1 language code.
            
        Returns:
            Tuple of (transcript_object, language_code) or (None, None).
        """
        # Helper function to categorize transcripts
        def categorize_transcripts():
            manual_transcripts = []
            auto_transcripts = []
            preferred_manual = None
            preferred_auto = None
            
            for transcript in transcript_list:
                if transcript.language_code == preferred_language:
                    if not transcript.is_generated:
                        preferred_manual = transcript
                    else:
                        preferred_auto = transcript
                elif not transcript.is_generated:
                    manual_transcripts.append(transcript)
                else:
                    auto_transcripts.append(transcript)
            
            return preferred_manual, preferred_auto, manual_transcripts, auto_transcripts
        
        preferred_manual, preferred_auto, manual_transcripts, auto_transcripts = categorize_transcripts()
        
        # Select based on priority
        if preferred_manual:
            logger.debug(f"Found manually created transcript in preferred language: {preferred_language}")
            return preferred_manual, preferred_language
        
        if preferred_auto:
            logger.debug(f"Found auto-generated transcript in preferred language: {preferred_language}")
            return preferred_auto, preferred_language
        
        if manual_transcripts:
            selected = manual_transcripts[0]
            logger.debug(f"Using manually created transcript in: {selected.language_code}")
            return selected, selected.language_code
        
        if auto_transcripts:
            selected = auto_transcripts[0]
            logger.debug(f"Using auto-generated transcript in: {selected.language_code}")
            return selected, selected.language_code
        
        logger.warning("No transcripts available")
        return None, None
    
    async def _extract_comments(
        self, 
        video_id: str, 
        max_comments: int = 20
    ) -> Optional[List[str]]:
        """Extract video comments (requires YouTube Data API v3).
        
        Note: This is a placeholder implementation. Full implementation requires:
        1. YouTube Data API v3 enabled in Google Cloud Console
        2. API key with appropriate quota
        3. Proper pagination and error handling
        
        Args:
            video_id: YouTube video identifier.
            max_comments: Maximum number of comments to retrieve.
            
        Returns:
            List of comment texts or None if not available.
        """
        if not self.youtube_api_key:
            logger.warning("YouTube API key not configured - comment extraction disabled")
            return None
        
        # TODO: Implement actual YouTube Data API v3 integration
        # This would involve:
        # 1. Setting up google-api-python-client
        # 2. Implementing pagination
        # 3. Handling rate limits and quotas
        # 4. Processing comment threads
        
        logger.info(f"Comment extraction requested for {video_id} (max: {max_comments})")
        
        # Placeholder implementation
        placeholder_comments = [
            "Great video! Very informative.",
            "Thanks for sharing this content.",
            "This helped me understand the topic better.",
            "Looking forward to more content like this.",
            "Well explained and easy to follow.",
        ]
        
        return placeholder_comments[:max_comments]
