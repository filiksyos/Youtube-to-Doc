"""Process a query by parsing YouTube URL and generating video documentation."""

from functools import partial
from typing import Optional, Dict

from fastapi import Request
from starlette.templating import _TemplateResponse

from ..youtubedoc.youtube_processor import YoutubeProcessor
from ..youtubedoc.schemas.video_schema import VideoQuery
from ..youtubedoc.utils.s3_uploader import upload_markdown_to_s3
from .server_config import EXAMPLE_VIDEOS, MAX_DISPLAY_SIZE, templates
from .server_utils import Colors
import os
from urllib.parse import urlparse, parse_qs


async def process_query(
    request: Request,
    input_text: str,
    max_transcript_length: int,
    include_comments: bool = False,
    language: str = "en",
    is_index: bool = False,
) -> _TemplateResponse:
    """
    Process a query by parsing YouTube URL and generating video documentation.

    Handle user input, process YouTube video data, and prepare
    a response for rendering a template with the processed results or an error message.

    Parameters
    ----------
    request : Request
        The HTTP request object.
    input_text : str
        Input text provided by the user, typically a YouTube URL.
    max_transcript_length : int
        Maximum length of transcript to include.
    include_comments : bool
        Whether to include video comments in the documentation.
    language : str
        Preferred language for transcript extraction.
    is_index : bool
        Flag indicating whether the request is for the index page.

    Returns
    -------
    _TemplateResponse
        Rendered template response containing the processed results or an error message.
    """
    template = "index.jinja" if is_index else "video.jinja"
    template_response = partial(templates.TemplateResponse, name=template)

    context = {
        "request": request,
        "video_url": input_text,
        "examples": EXAMPLE_VIDEOS if is_index else [],
        "default_transcript_length": max_transcript_length,
        "include_comments": include_comments,
        "language": language,
        "content": None,
        "content_url": None,
        "error_message": None,
        "result": False,
    }

    try:
        # Parse and validate YouTube URL
        query = VideoQuery(
            url=input_text,
            max_transcript_length=max_transcript_length,
            include_comments=include_comments,
            language=language
        )

        # Initialize YouTube processor
        processor = YoutubeProcessor()

        # Process the video
        video_info, transcript, comments = await processor.process_video(query)
        
        # Check if transcript extraction failed
        if transcript is None:
            print("WARNING: No transcript was extracted - checking reasons...")
        
        # Generate documentation content (markdown)
        content_md = _generate_documentation(video_info, transcript, comments, include_comments)

        # Compute object key: docs/youtube/{video_id}.md
        video_id = video_info.get("video_id") or _extract_video_id_from_url(input_text)
        object_key = f"docs/youtube/{video_id}.md" if video_id else f"docs/youtube/unknown.md"

        # Upload to S3; return URL or None
        content_url = upload_markdown_to_s3(content_md, object_key)

        # If uploaded, hide local content and expose buttons
        if content_url:
            context["content_url"] = content_url
            context["content"] = None
        else:
            # Keep local content visible if upload fails (simple behavior)
            if len(content_md) > MAX_DISPLAY_SIZE:
                content_md = (
                    f"(Content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters)\n" + content_md[:MAX_DISPLAY_SIZE]
                )
            context["content"] = content_md

        context["video_info"] = video_info
        context["result"] = True

        _print_success(
            url=input_text,
            title=video_info.get("title", "Unknown"),
            duration=video_info.get("duration", 0),
            transcript_length=len(transcript) if transcript else 0
        )

    except Exception as exc:
        _print_error(input_text, exc)
        context["error_message"] = f"Error processing video: {exc}"
        
        if "not available" in str(exc).lower():
            context["error_message"] = (
                "Video not available. Please check that the video is public and the URL is correct."
            )
        elif "transcript" in str(exc).lower():
            context["error_message"] = (
                "Transcript not available for this video. Try a different video or check if captions are enabled."
            )

    return template_response(context=context)


async def process_query_core(
    input_text: str,
    max_transcript_length: int,
    include_comments: bool = False,
    language: str = "en",
) -> Dict:
    """Process a query and return a context dict suitable for JSON responses.

    This mirrors the logic in process_query but returns plain data instead of
    a rendered template.
    """
    context: Dict[str, Optional[str] | bool | dict] = {
        "video_url": input_text,
        "default_transcript_length": max_transcript_length,
        "include_comments": include_comments,
        "language": language,
        "content": None,
        "content_url": None,
        "error_message": None,
        "result": False,
    }

    try:
        query = VideoQuery(
            url=input_text,
            max_transcript_length=max_transcript_length,
            include_comments=include_comments,
            language=language,
        )

        processor = YoutubeProcessor()
        video_info, transcript, comments = await processor.process_video(query)

        content_md = _generate_documentation(
            video_info, transcript, comments, include_comments
        )

        video_id = video_info.get("video_id") or _extract_video_id_from_url(input_text)
        object_key = (
            f"docs/youtube/{video_id}.md" if video_id else f"docs/youtube/unknown.md"
        )

        content_url = upload_markdown_to_s3(content_md, object_key)
        if content_url:
            context["content_url"] = content_url
            context["content"] = None
        else:
            if len(content_md) > MAX_DISPLAY_SIZE:
                content_md = (
                    f"(Content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters)\n"
                    + content_md[:MAX_DISPLAY_SIZE]
                )
            context["content"] = content_md

        context["video_info"] = video_info
        context["result"] = True

        _print_success(
            url=input_text,
            title=video_info.get("title", "Unknown"),
            duration=video_info.get("duration", 0),
            transcript_length=len(transcript) if transcript else 0,
        )
    except Exception as exc:
        _print_error(input_text, exc)
        context["error_message"] = f"Error processing video: {exc}"
        if "not available" in str(exc).lower():
            context["error_message"] = (
                "Video not available. Please check that the video is public and the URL is correct."
            )
        elif "transcript" in str(exc).lower():
            context["error_message"] = (
                "Transcript not available for this video. Try a different video or check if captions are enabled."
            )

    return context


def _extract_video_id_from_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        if parsed.netloc.endswith("youtube.com") and parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.netloc == "youtu.be":
            return parsed.path.lstrip("/") or None
    except Exception:
        return None
    return None


def _generate_documentation(
    video_info: dict,
    transcript: Optional[str],
    comments: Optional[list],
    include_comments: bool
) -> str:
    """
    Generate formatted documentation from video information.

    Parameters
    ----------
    video_info : dict
        Video metadata and information.
    transcript : Optional[str]
        Video transcript text.
    comments : Optional[list]
        Video comments if available.
    include_comments : bool
        Whether to include comments in documentation.

    Returns
    -------
    str
        Formatted documentation content.
    """
    doc_parts = []
    
    # Video header
    doc_parts.append("# YouTube Video Documentation\n")
    doc_parts.append(f"**Title:** {video_info.get('title', 'Unknown')}\n")
    doc_parts.append(f"**URL:** {video_info.get('url', 'Unknown')}\n")
    doc_parts.append(f"**Duration:** {_format_duration(video_info.get('duration', 0))}\n")
    doc_parts.append(f"**Views:** {video_info.get('view_count', 'Unknown')}\n")
    doc_parts.append(f"**Channel:** {video_info.get('channel', 'Unknown')}\n")
    doc_parts.append(f"**Upload Date:** {video_info.get('upload_date', 'Unknown')}\n\n")
    
    # Description
    if video_info.get('description'):
        doc_parts.append("## Description\n")
        doc_parts.append(f"{video_info['description']}\n\n")
    
    # Transcript
    if transcript:
        doc_parts.append("## Transcript\n")
        doc_parts.append(f"{transcript}\n\n")
    
    # Comments
    if include_comments and comments:
        doc_parts.append("## Comments\n")
        for i, comment in enumerate(comments[:20], 1):  # Limit to top 20 comments
            doc_parts.append(f"**Comment {i}:** {comment}\n\n")
    
    # Token estimation
    content = "".join(doc_parts)
    estimated_tokens = _estimate_tokens(content)
    doc_parts.append(f"**Estimated Tokens:** {estimated_tokens}\n")
    
    return "".join(doc_parts)


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs}s"


def _estimate_tokens(text: str) -> int:
    """Estimate token count for text content."""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except ImportError:
        # Fallback estimation: approximately 4 characters per token
        return len(text) // 4


def _print_success(url: str, title: str, duration: int, transcript_length: int) -> None:
    """Print success message with video details."""
    print(f"{Colors.GREEN}INFO{Colors.END}: {Colors.GREEN}<-  {Colors.END}", end="")
    print(f"{Colors.WHITE}{url:<50}{Colors.END}", end="")
    print(f" | {Colors.PURPLE}Title: {title[:30]}...{Colors.END}", end="")
    print(f" | {Colors.YELLOW}Duration: {_format_duration(duration)}{Colors.END}", end="")
    print(f" | {Colors.CYAN}Content: {transcript_length} chars{Colors.END}")


def _print_error(url: str, error: Exception) -> None:
    """Print error message with video URL."""
    print(f"{Colors.BROWN}WARN{Colors.END}: {Colors.RED}<-  {Colors.END}", end="")
    print(f"{Colors.WHITE}{url:<50}{Colors.END}", end="")
    print(f" | {Colors.RED}{error}{Colors.END}") 