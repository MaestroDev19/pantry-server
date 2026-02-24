from __future__ import annotations

from typing import List, Tuple
from uuid import UUID

from langchain_core.documents import Document
from langchain.tools import tool

from app.ai.retriever_cache import get_retriever_cache
from app.ai.vector_store import get_vector_store


# Shared LangChain retriever + cache for pantry RAG flows.
retriever = get_vector_store().as_retriever()
_cache = get_retriever_cache()


@tool(response_format="content_and_artifact")
def retrieve_pantry_items(
    query: str,
    k: int = 5,
    household_id: UUID | None = None,
) -> Tuple[str, List[Document]]:
    """
    Retrieve relevant pantry items from the Supabase-backed vector store
    to help answer a user query.

    Results are cached per-household and query to avoid redundant vector lookups.
    """
    household_key = str(household_id) if household_id is not None else "global"

    cached = _cache.get(household_key, query, k)
    if cached is not None:
        return cached

    documents = retriever.get_relevant_documents(query)[:k]
    serialized = "\n\n".join(doc.page_content for doc in documents)
    _cache.set(household_key, query, k, documents, serialized)
    return serialized, documents


retriever_tool = retrieve_pantry_items
