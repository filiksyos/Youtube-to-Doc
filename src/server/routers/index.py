"""This module defines the FastAPI router for the home page of the YouTube to Doc application."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ..query_processor import process_query
from ..server_config import EXAMPLE_VIDEOS, templates
from ..server_utils import limiter

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """
    Render the home page with example YouTube videos and default parameters.

    This endpoint serves the home page of the application, rendering the `index.jinja` template
    and providing it with a list of example YouTube videos and default values.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.

    Returns
    -------
    HTMLResponse
        An HTML response containing the rendered home page template, with example videos
        and other default parameters.
    """
    return templates.TemplateResponse(
        "index.jinja",
        {
            "request": request,
            "examples": EXAMPLE_VIDEOS,
            "default_transcript_length": 243,
        },
    )


@router.post("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def index_post(
    request: Request,
    input_text: str = Form(...),
    max_transcript_length: int = Form(...),
    include_comments: bool = Form(False),
    language: str = Form("en"),
) -> HTMLResponse:
    """
    Process the form submission with user input for YouTube video processing.

    This endpoint handles POST requests from the home page form. It processes the user-submitted
    input (e.g., YouTube URL, transcript length, language) and invokes the `process_query` function to handle
    the video processing logic, returning the result as an HTML response.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.
    input_text : str
        The YouTube URL provided by the user for processing.
    max_transcript_length : int
        The maximum transcript length specified by the user.
    include_comments : bool
        Whether to include video comments in the documentation.
    language : str
        The preferred language for transcript extraction.

    Returns
    -------
    HTMLResponse
        An HTML response containing the results of processing the YouTube video,
        which will be rendered and returned to the user.
    """
    return await process_query(
        request,
        input_text,
        max_transcript_length,
        include_comments,
        language,
        is_index=True,
    ) 