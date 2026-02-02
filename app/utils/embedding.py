from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings


embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001", api_key=settings.google_genai_api_key,output_dimensionality=768)

def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Get the embeddings instance."""
    return embeddings

__all__ = ["get_embeddings"]