"""This module defines the FastAPI router for dynamic YouTube video processing."""

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse

from ..query_processor import process_query
from ..server_utils import limiter

router = APIRouter()


@router.get("/video/{video_id}", response_class=HTMLResponse)
async def video_page(request: Request, video_id: str) -> HTMLResponse:
    """
    Render a page for a specific YouTube video.

    Parameters
    ----------
    request : Request
        The incoming request object.
    video_id : str
        The YouTube video ID.

    Returns
    -------
    HTMLResponse
        An HTML response containing the video processing form.
    """
    from ..server_config import templates
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return templates.TemplateResponse(
        "video.jinja",
        {
            "request": request,
            "video_url": video_url,
            "video_id": video_id,
            "default_transcript_length": 243,
        },
    )


@router.get("/watch", response_class=HTMLResponse)
async def watch_redirect(request: Request) -> HTMLResponse:
    """
    Support YouTube-style watch endpoint: /watch?v=VIDEO_ID
    Render the video page with URL prefilled; client will handle SSE processing.
    """
    from urllib.parse import parse_qs, urlparse
    from ..server_config import templates

    query = parse_qs(urlparse(str(request.url)).query)
    video_id = (query.get("v") or [None])[0]
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

    return templates.TemplateResponse(
        "video.jinja",
        {
            "request": request,
            "video_url": video_url,
            "video_id": video_id or "",
            "default_transcript_length": 10_000_000,
            "include_comments": False,
            "language": "en",
        },
    )





@router.post("/watch", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def process_watch(
    request: Request,
    input_text: str = Form(...),
) -> HTMLResponse:
    """
    Handle form submission from /watch page to generate documentation.
    """
    # Enforce full transcript in English without comments
    MAX_INT = 10_000_000
    return await process_query(
        request,
        input_text,
        MAX_INT,
        False,
        "en",
        is_index=False,
    )


@router.post("/video/{video_id}", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def process_video(
    request: Request,
    video_id: str,
) -> HTMLResponse:
    """
    Process a specific YouTube video.

    Parameters
    ----------
    request : Request
        The incoming request object.
    video_id : str
        The YouTube video ID.
    max_transcript_length : int
        The maximum transcript length.
    include_comments : bool
        Whether to include video comments.
    language : str
        The preferred language for transcript.

    Returns
    -------
    HTMLResponse
        An HTML response containing the processed video content.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Enforce full transcript in English without comments
    MAX_INT = 10_000_000
    return await process_query(
        request,
        video_url,
        MAX_INT,
        False,
        "en",
        is_index=False,
    )