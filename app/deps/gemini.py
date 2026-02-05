from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


@lru_cache(maxsize=1)
def get_gemini_client() -> ChatGoogleGenerativeAI:
    """
    Get or create the Gemini client instance.
    
    Uses LRU cache to ensure a single client instance is reused across requests.
    The client is thread-safe and can be safely shared.
    
    Returns:
        ChatGoogleGenerativeAI: Configured Gemini client instance
    """
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        max_tokens=settings.gemini_max_tokens,
        max_retries=settings.gemini_max_retries,
        api_key=settings.google_genai_api_key,
    )


__all__ = ["get_gemini_client"]