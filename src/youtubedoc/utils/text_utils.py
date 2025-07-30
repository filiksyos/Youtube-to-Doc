"""Text utilities for YouTube content processing."""

import re
from typing import Optional


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Parameters
    ----------
    text : str
        The text to clean.
        
    Returns
    -------
    str
        Cleaned text.
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might cause issues
    text = re.sub(r'[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\xff]', '', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with optional suffix.
    
    Parameters
    ----------
    text : str
        The text to truncate.
    max_length : int
        Maximum length of the text.
    suffix : str
        Suffix to add when truncating.
        
    Returns
    -------
    str
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.
    
    Parameters
    ----------
    text : str
        The text to analyze.
        
    Returns
    -------
    int
        Estimated token count.
    """
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except ImportError:
        # Fallback estimation: approximately 4 characters per token
        return max(1, len(text) // 4)


def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """
    Extract keywords from text content.
    
    Parameters
    ----------
    text : str
        The text to analyze.
    max_keywords : int
        Maximum number of keywords to extract.
        
    Returns
    -------
    list
        List of keywords.
    """
    if not text:
        return []
    
    # Simple keyword extraction (can be improved with NLP libraries)
    words = re.findall(r'\b\w{3,}\b', text.lower())
    
    # Remove common stop words
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
        'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 
        'how', 'man', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did',
        'its', 'let', 'put', 'say', 'she', 'too', 'use', 'way', 'may', 'come',
        'than', 'that', 'this', 'will', 'with', 'have', 'from', 'they', 'been',
        'said', 'each', 'which', 'their', 'time', 'about', 'would', 'there',
        'could', 'other', 'after', 'first', 'well', 'water', 'been', 'call',
        'who', 'oil', 'sit', 'now', 'find', 'long', 'down', 'day', 'did', 'get',
        'come', 'made', 'may', 'part'
    }
    
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    # Count frequency and return most common
    from collections import Counter
    word_counts = Counter(keywords)
    
    return [word for word, count in word_counts.most_common(max_keywords)] 