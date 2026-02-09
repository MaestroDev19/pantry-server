from __future__ import annotations

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from uuid import UUID
from supabase import Client
import anyio

try:
    from gotrue import User
except ImportError:
    from typing import Any
    User = Any  # type: ignore[misc, assignment]

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.deps.supabase import get_supabase_client

logger = get_logger(__name__)
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
        AppError: 401 if token is missing, invalid, or expired
    """
    if not credentials:
        logger.error("Missing authentication credentials")
        raise AppError(
            "Missing authentication credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_response = await anyio.to_thread.run_sync(
            lambda: supabase.auth.get_user(credentials.credentials)
        )

        if not user_response.user:
            logger.error("Invalid authentication credentials (no user in response)")
            raise AppError(
                "Invalid authentication credentials",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info("User authenticated", extra={"user_id": str(user_response.user.id)})
        return user_response.user

    except AppError:
        raise
    except Exception as e:
        logger.error("Could not validate credentials", exc_info=True)
        raise AppError(
            "Could not validate credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
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
        AppError: If the user's ID is missing or not a valid UUID.
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        logger.error("Authenticated user missing user ID")
        raise AppError("Authenticated user missing user ID", status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        uuid_obj = UUID(str(user_id))
    except Exception:
        logger.error("Authenticated user has invalid user ID", extra={"user_id": str(user_id)})
        raise AppError("Authenticated user has invalid user ID", status_code=status.HTTP_401_UNAUTHORIZED)
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
        AppError: If the user's ID is missing or not a valid UUID.
    """
    # Guard against missing user id from Supabase
    if not user_id:
        logger.error("get_current_household_id: missing user_id")
        raise AppError("Authenticated user missing user ID", status_code=status.HTTP_401_UNAUTHORIZED)

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
        logger.error("Failed to resolve household membership", extra={"user_id": str(user_id)}, exc_info=True)
        raise AppError(
            "Failed to resolve household membership",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if not getattr(response, "data", None):
        logger.error("User is not a member of any household", extra={"user_id": str(user_id)})
        raise AppError("User is not a member of any household", status_code=status.HTTP_401_UNAUTHORIZED)

    household_id = UUID(response.data[0]["household_id"])
    logger.info("Resolved household for user", extra={"user_id": str(user_id), "household_id": str(household_id)})
    return household_id


