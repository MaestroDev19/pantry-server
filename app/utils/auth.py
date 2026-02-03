from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.services.supabase import get_supabase_client

auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    supabase: Client = Depends(get_supabase_client),
) -> Any:
    """
    Dependency to get the current authenticated user from Supabase.
    
    Validates the Bearer token and returns the user object.
    Uses anon key client to respect Row Level Security policies.
    
    Args:
        credentials: HTTP Bearer token credentials from request header
        supabase: Supabase client instance (injected via dependency)
        
    Returns:
        Authenticated user object from Supabase (contains id, email, user_metadata, etc.)
        
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_response = supabase.auth.get_user(credentials.credentials)
        
        if not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user_response.user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e