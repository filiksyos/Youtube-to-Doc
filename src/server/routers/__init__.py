"""Router package initialization."""

from .index import router as index
from .dynamic import router as dynamic

__all__ = ["index", "dynamic"] 