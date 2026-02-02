from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

_client = None

def get_gemini_client() -> ChatGoogleGenerativeAI:
    """Initialize and cache the Gemini client."""
    global _client

    if _client is None:
        _client = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            max_tokens=None,
            max_retries=2,
            api_key=settings.google_genai_api_key
        )
    return _client