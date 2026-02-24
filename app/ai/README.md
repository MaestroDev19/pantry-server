# ai

AI and vector store integration used by services (e.g. pantry embeddings, search, recipe generation).

## Modules

- **vector_store.py** — Vector store factory/access (Supabase + LangChain `SupabaseVectorStore` for semantic search).
- **retriever_cache.py** — In-memory cache for LangChain retrieval results, keyed by household + query, invalidated by pantry writes.
- **retriver.py** — LangChain tool wrapping the pantry vector store (`retrieve_pantry_items`), with optional household-scoped caching.
- **prompts.py** — Recipe generation prompts and helpers for building structured Gemini prompts from pantry items and user preferences.
