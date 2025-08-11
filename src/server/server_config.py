"""Configuration for the YouTube to Doc server."""

from typing import Dict, List

from fastapi.templating import Jinja2Templates

MAX_DISPLAY_SIZE: int = 300_000
DELETE_CACHE_AFTER: int = 60 * 60  # In seconds

EXAMPLE_VIDEOS: List[Dict[str, str]] = [
    {"name": "Python Tutorial", "url": "https://www.youtube.com/watch?v=_uQrJ0TkZlc"},
    {"name": "FastAPI Crash Course", "url": "https://www.youtube.com/watch?v=7t2alSnE2-I"},
    {"name": "Machine Learning Basics", "url": "https://www.youtube.com/watch?v=Gv9_4yMHFhI"},
    {"name": "JavaScript ES6", "url": "https://www.youtube.com/watch?v=WZQc7RUAg18"},
]

import os
from pathlib import Path

# Get the absolute path to templates directory
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) 