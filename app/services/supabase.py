from __future__ import annotations

from fastapi import Depends
from functools import lru_cache
from app.core.config import settings
from supabase import Client, create_client

@lru_cache()
def get_supabase_client() -> Client:
    """
    FastAPI dependency to create and return a Supabase client instance.
    
    Uses the anon key to respect Row Level Security policies.
    Suitable for user-authenticated operations.
    
    Returns:
        Client: Supabase client configured with anon key
        
    Raises:
        ValueError: If required environment variables are not set
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise ValueError(
            "Supabase URL and ANON_KEY must be set in environment variables"
        )
    
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache()
def get_supabase_service_role_client() -> Client:
    """
    FastAPI dependency to create and return a Supabase service role client instance.
    
    Uses the service role key which bypasses Row Level Security.
    Use only for administrative operations or when RLS bypass is required.
    
    Returns:
        Client: Supabase client configured with service role key
        
    Raises:
        ValueError: If required environment variables are not set
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError(
            "Supabase URL and SERVICE_ROLE_KEY must be set in environment variables"
        )
    
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


__all__ = ["get_supabase_client", "get_supabase_service_role_client"]