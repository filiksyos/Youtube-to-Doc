"""This module defines the FastAPI router for dynamic YouTube video processing."""

from fastapi import APIRouter, Request, Form
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


@router.post("/video/{video_id}", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def process_video(
    request: Request,
    video_id: str,
    max_transcript_length: int = Form(...),
    include_comments: bool = Form(False),
    language: str = Form("en"),
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
    
    return await process_query(
        request,
        video_url,
        max_transcript_length,
        include_comments,
        language,
        is_index=False,
    ) 