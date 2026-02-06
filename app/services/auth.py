from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from uuid import UUID
from supabase import Client, User
import anyio
from app.deps.supabase import get_supabase_client

auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    supabase: Client = Depends(get_supabase_client),
) -> User:
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
        user_response = await anyio.to_thread.run_sync(
            lambda: supabase.auth.get_user(credentials.credentials)
        )

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
        
async def get_current_user_id(
    user: User = Depends(get_current_user),
) -> UUID:
    """
    Dependency to get the current authenticated user's ID from Supabase Auth.

    Args:
        user: The currently authenticated User object as returned by Supabase.

    Returns:
        The UUID for the authenticated user.

    Raises:
        HTTPException: If the user's ID is missing or not a valid UUID.
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user missing user ID",
        )
    try:
        uuid_obj = UUID(str(user_id))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has invalid user ID",
        )
    return uuid_obj

async def get_current_household_id(
    user_id: UUID = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase_client),
) -> UUID:
    """
    Dependency to get the current authenticated user's primary household ID.
    Uses the Supabase auth user id to respect RLS policies.

    Args:
        user_id: The UUID for the authenticated user.
        supabase: The Supabase client instance.

    Returns:
        The UUID for the authenticated user's primary household.

    Raises:
        HTTPException: If the user's ID is missing or not a valid UUID.
    """
    # Guard against missing user id from Supabase
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user missing user ID",
        )

    try:
        response = await anyio.to_thread.run_sync(
            lambda: (
                supabase.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to resolve household membership",
        ) from exc

    if not getattr(response, "data", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not a member of any household",
        )

    return UUID(response.data[0]["household_id"])


