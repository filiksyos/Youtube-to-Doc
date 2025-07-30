"""Server utilities for the YouTube to Doc application."""

import math
from contextlib import asynccontextmanager
from typing import Generator

from fastapi import Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address


class Colors:
    """ANSI color codes for console output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BROWN = '\033[38;5;130m'
    END = '\033[0m'


def get_client_ip(request: Request) -> str:
    """
    Get the client IP address from the request.
    
    Parameters
    ----------
    request : Request
        The incoming HTTP request.
        
    Returns
    -------
    str
        The client IP address.
    """
    return get_remote_address(request)


# Initialize the rate limiter
limiter = Limiter(key_func=get_client_ip)


async def rate_limit_exception_handler(request: Request, exc):
    """
    Handle rate limit exceeded exceptions.
    
    Parameters
    ----------
    request : Request
        The incoming HTTP request.
    exc : Exception
        The rate limit exception.
        
    Returns
    -------
    Response
        A response indicating the rate limit was exceeded.
    """
    return await _rate_limit_exceeded_handler(request, exc)


def log_slider_to_size(slider_value: int) -> int:
    """
    Convert slider value to file size in bytes using logarithmic scaling.
    
    Parameters
    ----------
    slider_value : int
        The slider position value.
        
    Returns
    -------
    int
        The corresponding file size in bytes.
    """
    if slider_value <= 0:
        return 1024  # 1KB minimum
    
    # Logarithmic scale: slider_value 0-500 maps to 1KB-10MB
    min_size = 1024  # 1KB
    max_size = 10 * 1024 * 1024  # 10MB
    
    # Use logarithmic scaling
    log_min = math.log(min_size)
    log_max = math.log(max_size)
    
    # Normalize slider value to 0-1
    normalized = slider_value / 500.0
    
    # Apply logarithmic scaling
    log_size = log_min + normalized * (log_max - log_min)
    
    return int(math.exp(log_size))


@asynccontextmanager
async def lifespan(app) -> Generator:
    """
    Application lifespan manager.
    
    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.
        
    Yields
    ------
    None
        Yields control during application lifetime.
    """
    # Startup
    print(f"{Colors.GREEN}YouTube to Doc server starting up...{Colors.END}")
    
    yield
    
    # Shutdown
    print(f"{Colors.RED}YouTube to Doc server shutting down...{Colors.END}") 