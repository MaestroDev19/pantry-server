from langchain_community.vectorstores import SupabaseVectorStore
from app.utils.embedding import embeddings_client
from app.deps.supabase import get_supabase_client


def get_vector_store() -> SupabaseVectorStore:
    """
    Get or create the vector store instance.
    """
    
    
    return SupabaseVectorStore(
        client=get_supabase_client(),
        embedding=embeddings_client(),
        table_name="pantry_embeddings",
        query_name="match_pantry_items",
    )