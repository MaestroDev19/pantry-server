from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import anyio
from fastapi import status
from supabase import Client

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.ai.vector_store import get_vector_store
from app.models.pantry import (
    PantryItem,
    PantryItemCreate,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
    BulkUpsertResult,
)
from app.utils.date_time_styling import format_iso_date, format_iso_datetime
from app.utils.embedding import embeddings_client

logger = get_logger(__name__)


async def _ensure_user_in_household(
    supabase: Client, user_id: UUID, household_id: UUID, operation: str
) -> None:
    membership_response = await anyio.to_thread.run_sync(
        lambda: (
            supabase.table("household_members")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("household_id", str(household_id))
            .limit(1)
            .execute()
        )
    )
    if not getattr(membership_response, "data", None):
        logger.error(
            f"{operation}: user not in household",
            extra={"household_id": str(household_id), "user_id": str(user_id)},
        )
        raise AppError(
            "User is not a member of the specified household",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _embedding_content_for_row(row: Dict[str, Any]) -> str:
    name = row.get("name") or ""
    category = row.get("category") or ""
    return f"{name} {category}".strip()


def _embedding_metadata_for_row(row: Dict[str, Any]) -> Dict[str, Optional[str]]:
    name = row.get("name") or ""
    category = row.get("category") or ""
    expiry_raw = row.get("expiry_date")
    return {
        "pantry_item_id": str(row["id"]) if row.get("id") is not None else None,
        "name": name or None,
        "category": category or None,
        "quantity": str(row["quantity"]) if row.get("quantity") is not None else None,
        "unit": row.get("unit"),
        "expiry_date": (
            format_iso_date(value=expiry_raw) if expiry_raw is not None else None
        ),
        "owner_id": str(row["owner_id"]) if row.get("owner_id") is not None else None,
        "household_id": (
            str(row["household_id"]) if row.get("household_id") is not None else None
        ),
        "expiry_visible": row.get("expiry_visible"),
    }


class PantryService:
    def __init__(self, supabase: Client) -> None:
        # Store the Supabase database client for later use in data operations.
        self.supabase = supabase
        # Instantiate the vector store for semantic search (not directly used in these methods, but available for extensibility).
        self.vector_store = get_vector_store()
        # Instantiate the embedding client for vectorizing pantry items during creation/update.
        self.embeddings_client = embeddings_client()

    async def add_pantry_item_single(
        self,
        pantry_item: PantryItemUpsert,
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemUpsertResponse:
        """
        Add a single pantry item to the database for a specific household and user. 
        Generates a semantic vector embedding for the item and inserts it into the embeddings table.

        Args:
            pantry_item (PantryItemUpsert): The item details as validated input.
            household_id (UUID): The household to which the item is being added.
            user_id (UUID): The user claiming/owning this item.

        Returns:
            PantryItemUpsertResponse: Contains item id, success/failure, quantities, and embedding status.
        """
        await _ensure_user_in_household(
            self.supabase, user_id, household_id, "Add pantry item"
        )

        data = pantry_item.model_dump()
        data["household_id"] = str(household_id)
        data["owner_id"] = str(user_id)
        data["created_at"] = format_iso_datetime(value=datetime.now())
        data["updated_at"] = format_iso_datetime(value=datetime.now())
        data["expiry_date"] = (
            format_iso_date(value=data["expiry_date"]) if data["expiry_date"] else None
        )

        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .upsert(data)
                        .execute()
                )
            )
        except Exception as exc:
            logger.error("Failed to create pantry item (db/network)", exc_info=True, extra={"household_id": str(household_id)})
            raise AppError("Failed to create pantry item", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        if not getattr(response, "data", None):
            logger.error("Pantry item upsert returned no data", extra={"household_id": str(household_id)})
            raise AppError("Pantry item was not created", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        row = response.data[0]
        logger.debug("Pantry item upserted", extra={"item_id": row.get("id"), "household_id": str(household_id)})

        embedding_generated = False
        try:
            content = _embedding_content_for_row(row)
            metadata = _embedding_metadata_for_row(row)

            embeddings: List[List[float]] = await anyio.to_thread.run_sync(
                lambda: self.embeddings_client.embed_documents([content])
            )
            # Pick the embedding for this one item, or None if failed
            embedding_vector = embeddings[0] if embeddings else None
            if embedding_vector is not None:
                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table("pantry_embeddings")
                            .upsert(
                                {
                                    "pantry_item_id": row["id"],
                                    "content": content,
                                    "metadata": metadata,
                                    "embedding": embedding_vector,
                                    "created_at": format_iso_datetime(value=datetime.now()),
                                }
                            )
                            .execute()
                    )
                )
                embedding_generated = True
        except Exception:
            embedding_generated = False

        logger.info("Pantry item added", extra={"item_id": row.get("id"), "household_id": str(household_id), "embedding_generated": embedding_generated})
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=True,
            old_quantity=0,
            new_quantity=float(row.get("quantity") or 0),
            message="Pantry item added successfully",
            embedding_generated=embedding_generated,
        )

    async def add_pantry_item_bulk(
        self,
        pantry_items: List[PantryItemCreate],
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemsBulkCreateResponse:
        """
        Bulk insert pantry items for a household/user and generate embeddings in batch. 
        Reports counts and per-item bulk status.
        """
        await _ensure_user_in_household(
            self.supabase, user_id, household_id, "Bulk add"
        )

        rows_to_upsert: List[Dict[str, object]] = []
        for item in pantry_items:
            data = item.model_dump()
            data["household_id"] = str(household_id)
            data["owner_id"] = str(user_id)
            data["created_at"] = format_iso_datetime(value=datetime.now())
            data["updated_at"] = format_iso_datetime(value=datetime.now())
            data["expiry_date"] = format_iso_date(value=data["expiry_date"]) if data["expiry_date"] else None
            rows_to_upsert.append(data)

        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .upsert(rows_to_upsert)
                        .execute()
                )
            )
        except Exception as exc:
            logger.error("Bulk pantry create failed (db/network)", exc_info=True, extra={"household_id": str(household_id), "count": len(pantry_items)})
            raise AppError("Failed to create pantry items", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        if not getattr(response, "data", None):
            logger.error("Bulk pantry upsert returned no data", extra={"household_id": str(household_id)})
            raise AppError("Pantry items were not created", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        created_rows: List[Dict[str, Any]] = list(response.data)

        contents: List[str] = []
        metadatas: List[Dict[str, Optional[str]]] = []
        for row in created_rows:
            contents.append(_embedding_content_for_row(row))
            metadatas.append(_embedding_metadata_for_row(row))

        embeddings_queued = 0
        try:
            # Batch vectorize all item texts (blocking, so done in threadpool)
            embeddings: List[List[float]] = await anyio.to_thread.run_sync(
                lambda: self.embeddings_client.embed_documents(contents)
            )
            # Each embedding must be paired with its row and its metadata
            embedding_rows: List[Dict[str, object]] = []
            for row, content, metadata, embedding_vector in zip(
                created_rows, contents, metadatas, embeddings
            ):
                if not embedding_vector:
                    continue
                embedding_rows.append(
                    {
                        "pantry_item_id": row["id"],
                        "content": content,
                        "metadata": metadata,
                        "embedding": embedding_vector,
                    }
                )

            if embedding_rows:
                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table("pantry_embeddings")
                            .upsert(embedding_rows)
                            .execute()
                    )
                )
                embeddings_queued = len(embedding_rows)
        except Exception:
            embeddings_queued = 0

        bulk_results: List[BulkUpsertResult] = []
        for row in created_rows:
            bulk_results.append(
                BulkUpsertResult(
                    name=row.get("name") or "",
                    success=True,
                    is_new=True,
                    item_id=row.get("id"),
                    old_quantity=0.0,
                    new_quantity=float(row.get("quantity") or 0),
                    error=None,
                )
            )

        total_requested = len(pantry_items)
        successful = len(bulk_results)
        failed = total_requested - successful

        logger.info("Bulk pantry items added", extra={"household_id": str(household_id), "successful": successful, "total": total_requested, "embeddings_queued": embeddings_queued})
        return PantryItemsBulkCreateResponse(
            total_requested=total_requested,
            successful=successful,
            failed=failed,
            new_items=successful,
            updated_items=0,
            results=bulk_results,
            embeddings_queued=embeddings_queued,
        )

    async def get_my_pantry_items(self, household_id: UUID, user_id: UUID) -> List[PantryItem]:
        """
        Retrieve all pantry items for a specific user in a specific household.

        Args:
            household_id (UUID): The household's unique identifier.
            user_id (UUID): The owner's unique identifier.

        Returns:
            List[PantryItem]: All items found owned by that user in that household.
        """
        try:
            # Query for all items matching both household and user
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .select("*")
                        .eq("household_id", str(household_id))
                        .eq("owner_id", str(user_id))
                        .execute()
                )
            )
        except Exception as exc:
            logger.error("Failed to fetch pantry items", exc_info=True, extra={"household_id": str(household_id), "user_id": str(user_id)})
            raise AppError("Failed to fetch pantry items", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        # Return data list from response or empty if none
        return response.data or []

    async def get_household_pantry_items(self, household_id: UUID) -> List[PantryItem]:
        """
        Retrieve all pantry items for all users of a specific household.

        Args:
            household_id (UUID): Unique id for the household.

        Returns:
            List[PantryItem]: All items tied to that household, regardless of owner.
        """
        try:
            # Query for all pantry items associated with the specified household id
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .select("*")
                        .eq("household_id", str(household_id))
                        .execute()
                )
            )
        except Exception as exc:
            logger.error("Failed to fetch household pantry items", exc_info=True, extra={"household_id": str(household_id)})
            raise AppError("Failed to fetch household pantry items", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        return response.data or []
    
    async def update_pantry_item(self, pantry_item: PantryItemUpsert, household_id: UUID, user_id: UUID) -> PantryItemUpsertResponse:
        """
        Update an existing pantry item for the given user and household.
        Performs update where both household_id and owner_id match for security.

        Args:
            pantry_item (PantryItemUpsert): The item data to be updated.
            household_id (UUID): Restrict update within this household.
            user_id (UUID): The owner to match for authorization.

        Returns:
            PantryItemUpsertResponse: Database row(s) as returned from update (could weigh improving this).
        """
        try:
            # Issue an update, restricting by both household and owner id.
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .update(pantry_item.model_dump())
                    .eq("household_id", str(household_id))
                    .eq("owner_id", str(user_id))
                    .execute()
                )
            )
        except Exception as exc:
            logger.error("Failed to update pantry item", exc_info=True, extra={"household_id": str(household_id), "user_id": str(user_id)})
            raise AppError("Failed to update pantry item", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        if not getattr(response, "data", None):
            logger.error("Update pantry item: not found or not owned", extra={"household_id": str(household_id), "user_id": str(user_id)})
            raise AppError("Pantry item not found or not owned by user", status_code=status.HTTP_404_NOT_FOUND)

        row = response.data[0]
        logger.info("Pantry item updated", extra={"item_id": str(row.get("id")), "household_id": str(household_id)})
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=False,
            old_quantity=0.0,
            new_quantity=float(row.get("quantity") or 0),
            message="Pantry item updated successfully",
            embedding_generated=False,
        )
    
    async def delete_pantry_item(self, item_id: UUID, household_id: UUID, user_id: UUID) -> PantryItemUpsertResponse:
        """
        Delete a pantry item for the given user and household.
        Performs delete where both household_id and owner_id match for security.

        Args:
            item_id (UUID): The ID of the item to delete.
            household_id (UUID): Restrict delete within this household.
            user_id (UUID): The owner to match for authorization.

        Returns:
            PantryItemUpsertResponse: Summary of the delete operation.
        """
        try:
            # Issue a delete, restricting by both household and owner id.
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .delete()
                    .eq("id", str(item_id))
                    .eq("household_id", str(household_id))
                    .eq("owner_id", str(user_id))
                    .execute()
                )
            )
        except Exception as exc:
            logger.error("Failed to delete pantry item", exc_info=True, extra={"item_id": str(item_id), "household_id": str(household_id)})
            raise AppError("Failed to delete pantry item", status_code=status.HTTP_502_BAD_GATEWAY) from exc

        if not getattr(response, "data", None):
            logger.error("Delete pantry item: not found or not owned", extra={"item_id": str(item_id), "household_id": str(household_id)})
            raise AppError("Pantry item not found or not owned by user", status_code=status.HTTP_404_NOT_FOUND)

        row = response.data[0]
        logger.info("Pantry item deleted", extra={"item_id": str(item_id), "household_id": str(household_id)})
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=False,
            old_quantity=float(row.get("quantity") or 0),
            new_quantity=0.0,
            message="Pantry item deleted successfully",
            embedding_generated=False,
        )