from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Client:
    """Create and return a Supabase client instance."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise ValueError("Supabase URL and KEY must be set in environment variables")
    
    return create_client(settings.supabase_url, settings.supabase_anon_key)

__all__ = ["get_supabase_client"]