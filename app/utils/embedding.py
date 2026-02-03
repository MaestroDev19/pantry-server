from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings


@lru_cache(maxsize=1)
def embeddings_client() -> GoogleGenerativeAIEmbeddings:
    """
    Get or create the embeddings client instance.
    
    Uses LRU cache to ensure a single client instance is reused across requests.
    The client is thread-safe and can be safely shared.
    
    Returns:
        GoogleGenerativeAIEmbeddings: Configured embeddings client instance
    """
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embeddings_model,
        api_key=settings.google_genai_api_key,
        output_dimensionality=settings.gemini_embeddings_output_dimensionality,
    )


__all__ = ["embeddings_client"]

