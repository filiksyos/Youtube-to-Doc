"""This module defines the FastAPI router for dynamic YouTube video processing."""

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from ..query_processor import process_query, _generate_documentation, _extract_video_id_from_url
from ..server_utils import limiter
from ...youtubedoc.youtube_processor import YoutubeProcessor
from ...youtubedoc.schemas.video_schema import VideoQuery

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


@router.get("/api/process")
async def check_process(
    url: str = Query(..., description="YouTube video URL"),
    check_cache_only: bool = Query(False, description="Only check cache, don't process"),
    max_transcript_length: int = Query(10000),
    include_comments: bool = Query(False),
    language: str = Query("en"),
):
    """Check if video documentation is cached or process it."""
    
    # If not checking cache only, return error (this endpoint is for cache checks)
    if not check_cache_only:
        return {"error": "This endpoint is for cache checking only"}
    
    try:
        # Validate URL and extract video ID
        query = VideoQuery(
            url=url,
            max_transcript_length=max_transcript_length,
            include_comments=include_comments,
            language=language,
        )
        video_id = query.extract_video_id()
        if not video_id:
            return {"error": "Invalid YouTube URL", "cached": False}
        
        # Check cache
        object_key = f"docs/youtube/{video_id}.md"
        
        try:
            from ...youtubedoc.utils.s3_uploader import check_cached_documentation
            cached_url = check_cached_documentation(object_key)
            if cached_url:
                return {
                    "cached": True,
                    "content_url": cached_url,
                    "video_id": video_id,
                    "message": "Found in cache"
                }
            else:
                return {
                    "cached": False,
                    "video_id": video_id,
                    "message": "Not cached"
                }
        except Exception as exc:
            return {
                "cached": False,
                "video_id": video_id,
                "message": f"Cache check failed: {exc}"
            }
            
    except Exception as exc:
        return {"error": f"Invalid URL: {exc}", "cached": False}


@router.get("/api/process/stream")
async def stream_process(
    url: str = Query(..., description="YouTube video URL"),
    max_transcript_length: int = Query(10000),
    include_comments: bool = Query(False),
    language: str = Query("en"),
):
    """Server-Sent Events stream for processing a video with step-wise updates."""

    async def event_generator():
        import asyncio
        
        def sse(data: dict) -> str:
            import json
            return f"data: {json.dumps(data)}\n\n"
        
        # Send initial connection event to establish stream
        yield sse({"status": "connected", "message": "Connection established"})
        await asyncio.sleep(0.1)  # Small delay to prevent buffering

        # Step 0: URL validation
        yield sse({"status": "url_validation", "message": "Validating URL..."})
        await asyncio.sleep(0.1)
        try:
            query = VideoQuery(
                url=url,
                max_transcript_length=max_transcript_length,
                include_comments=include_comments,
                language=language,
            )
            video_id = query.extract_video_id()
            if not video_id:
                raise ValueError("Invalid YouTube URL")
            yield sse(
                {
                    "status": "url_validated",
                    "message": "URL validated",
                    "video_id": video_id,
                }
            )
        except Exception as exc:
            yield sse({"status": "error", "error": f"Invalid URL: {exc}"})
            return

        # Step 1: Cache check
        yield sse({"status": "cache_check", "message": "Checking cache..."})
        await asyncio.sleep(0.1)
        object_key = f"docs/youtube/{video_id}.md"
        
        try:
            from ...youtubedoc.utils.s3_uploader import check_cached_documentation
            cached_url = check_cached_documentation(object_key)
            if cached_url:
                yield sse({
                    "status": "complete",
                    "message": "Found in cache",
                    "content_url": cached_url,
                    "video_id": video_id,
                    "cached": True
                })
                return
            else:
                yield sse({"status": "cache_miss", "message": "Not cached, processing..."})
        except Exception as exc:
            yield sse({"status": "cache_miss", "message": "Cache check failed, processing..."})

        processor = YoutubeProcessor()

        # Step 1: Video metadata
        yield sse(
            {"status": "video_metadata", "message": "Extracting video metadata..."}
        )
        try:
            video_info = await processor._get_video_info(video_id, url)  # type: ignore[attr-defined]
            yield sse(
                {
                    "status": "video_metadata_done",
                    "message": "Video metadata extracted",
                    "title": video_info.get("title"),
                }
            )
        except Exception as exc:
            yield sse({"status": "error", "error": f"Metadata error: {exc}"})
            return

        # Step 2: Transcript
        yield sse(
            {
                "status": "transcript_processing",
                "message": "Processing transcript...",
            }
        )
        transcript = None
        try:
            transcript = await processor._get_transcript(  # type: ignore[attr-defined]
                video_id, language, max_transcript_length
            )
            yield sse(
                {
                    "status": "transcript_done",
                    "message": "Transcript processed",
                    "length": len(transcript) if transcript else 0,
                }
            )
        except Exception as exc:
            # Non-fatal: continue without transcript
            yield sse(
                {
                    "status": "transcript_skipped",
                    "message": f"Transcript not available: {exc}",
                }
            )

        # Step 3: Documentation generation
        yield sse(
            {
                "status": "doc_generation",
                "message": "Generating documentation...",
            }
        )
        try:
            content_md = _generate_documentation(
                video_info, transcript, None, include_comments
            )
            yield sse(
                {
                    "status": "doc_generated",
                    "message": "Documentation generated",
                    "size": len(content_md),
                }
            )
        except Exception as exc:
            yield sse({"status": "error", "error": f"Generation error: {exc}"})
            return

        # Step 4: S3 upload
        yield sse(
            {"status": "s3_upload", "message": "Uploading to cloud storage..."}
        )
        try:
            from ...youtubedoc.utils.s3_uploader import upload_markdown_to_s3

            object_key = (
                f"docs/youtube/{video_id}.md" if video_id else f"docs/youtube/unknown.md"
            )
            content_url = upload_markdown_to_s3(content_md, object_key)
            if content_url:
                yield sse(
                    {
                        "status": "complete",
                        "message": "Upload complete",
                        "content_url": content_url,
                        "video_id": video_id,
                    }
                )
            else:
                yield sse(
                    {
                        "status": "complete",
                        "message": "Completed with local content",
                        "content": content_md,
                        "video_id": video_id,
                    }
                )
        except Exception as exc:
            yield sse({"status": "error", "error": f"Upload error: {exc}"})
            return

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
        "Content-Encoding": "identity",  # Disable compression
        "Transfer-Encoding": "chunked"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


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