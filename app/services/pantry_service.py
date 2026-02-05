from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime
from utils.date_time_styling import format_iso_datetime, format_iso_date, format_display_date
import anyio  # Library to provide asynchronous concurrency
from fastapi import HTTPException, status  # For HTTP error handling and status codes
from supabase import Client  # Supabase client to interact with the database

from ai.vector_store import get_vector_store  # Function to retrieve a vector store instance
from models.pantry import (
    PantryItem,
    PantryItemCreate,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
    BulkUpsertResult,
)  # Importing data models used to represent pantry items and related requests/responses
from utils.embedding import embeddings_client  # Utility for embedding-related operations


class PantryService:
    def __init__(self, supabase: Client) -> None:
        # Initialize the PantryService with a Supabase database client.
        self.supabase = supabase
        # Initialize the vector store (possibly for semantic search, not used here directly but useful for extension)
        self.vector_store = get_vector_store()
        # Initialize the embeddings client (for generating item embeddings, not used directly here)
        self.embeddings_client = embeddings_client()

    async def add_pantry_item_single(
        self,
        pantry_item: PantryItemUpsert,
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemUpsertResponse:
        """
        Adds a single pantry item to the database for the specified household and user.

        Args:
            pantry_item (PantryItemUpsert): The item details to be added.
            household_id (UUID): Identifier for the household where this item belongs.
            user_id (UUID): Identifier for the user that owns this item.

        Returns:
            PantryItemUpsertResponse: Represents status and metadata about the upsert operation.
        """
        # Ensure the requesting user belongs to the target household, matching RLS constraints
        membership_response = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("household_members")
                .select("id")
                .eq("user_id", str(user_id))
                .eq("household_id", str(household_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(membership_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the specified household",
            )

        # Convert the PantryItemCreate pydantic model to a dictionary
        data = pantry_item.model_dump()
        # Attach household and owner identity to the item data
        data["household_id"] = str(household_id)
        data["owner_id"] = str(user_id) 
        data["created_at"] = format_iso_datetime(value=datetime.now())
        data["updated_at"] = format_iso_datetime(value=datetime.now())
        data["expiry_date"] = format_iso_date(value=data["expiry_date"]) if data["expiry_date"] else None
        try:
            # Upsert the data into the 'pantry_items' table in the database using the Supabase client.
            # .upsert(data) updates the row if it already exists, otherwise inserts a new row.
            # .select("*") returns all columns for the row.
            # Use anyio.to_thread.run_sync to run the synchronous operation in a thread so as not to block the event loop.
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .upsert(data)
                    .select("*")
                    .execute()
                )
            )
        except Exception as exc:  # Catch any exception that occurs during insert
            # Raise an HTTPException with 502 BAD_GATEWAY if the insert fails (possibly due to a DB/network issue)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create pantry item",
            ) from exc

        # If the response does not include data (item not created), respond with server error
        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pantry item was not created",
            )

        # Extract the first row from the returned data (the inserted pantry item)
        row = response.data[0]
        print(row)

        # Attempt to generate and store an embedding for the new pantry item
        embedding_generated = False
        try:
            # Build the content string similar to the database trigger logic
            name = row.get("name") or ""
            category = row.get("category") or ""
            content = f"{name} {category}".strip()

            # Build metadata payload for the embeddings table
            metadata: Dict[str, Optional[str]] = {
                "pantry_item_id": str(row.get("id")) if row.get("id") is not None else None,
                "name": name or None,
                "category": category or None,
                "quantity": str(row.get("quantity")) if row.get("quantity") is not None else None,
                "unit": row.get("unit"),
                "expiry_date": (
                    format_iso_date(value=row.get("expiry_date"))
                    if row.get("expiry_date") is not None
                    else None
                ),
                "owner_id": str(row.get("owner_id")) if row.get("owner_id") is not None else None,
                "household_id": (
                    str(row.get("household_id")) if row.get("household_id") is not None else None
                ),
                "expiry_visible": row.get("expiry_visible"),
            }

            # Generate embedding vector for the content
            embeddings: List[List[float]] = await anyio.to_thread.run_sync(
                lambda: self.embeddings_client.embed_documents([content])
            )
            embedding_vector = embeddings[0] if embeddings else None

            if embedding_vector is not None:
                # Upsert into the pantry_embeddings table with the generated embedding
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

        # Return a PantryItemUpsertResponse containing information about the operation.
        return PantryItemUpsertResponse(
            id=row["id"],  # The unique identifier of the new pantry item
            is_new=True,  # Indicates this was a new insert and not an update
            old_quantity=0,  # As it's a new item, previous quantity is 0
            new_quantity=float(row.get("quantity") or 0),  # Set the new quantity (default to 0 if None)
            message="Pantry item added successfully",  # Success message
            embedding_generated=embedding_generated,
        )
    async def add_pantry_item_bulk(
        self,
        pantry_items: List[PantryItemCreate],
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemsBulkCreateResponse:
        """
        Adds multiple pantry items to the database for the specified household and user.
        Performs a bulk upsert to Supabase and generates embeddings in batch.
        """
        # Ensure the requesting user belongs to the target household, matching RLS constraints
        membership_response = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("household_members")
                .select("id")
                .eq("user_id", str(user_id))
                .eq("household_id", str(household_id))
                .limit(1)
                .execute()
            )
        )
        if not getattr(membership_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the specified household",
            )

        # Prepare rows for bulk upsert into pantry_items
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
            # Bulk upsert all items in a single call
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .upsert(rows_to_upsert)
                    .select("*")
                    .execute()
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create pantry items",
            ) from exc

        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pantry items were not created",
            )

        created_rows: List[Dict] = list(response.data)

        # Build contents and metadata for embeddings
        contents: List[str] = []
        metadatas: List[Dict[str, Optional[str]]] = []
        for row in created_rows:
            name = row.get("name") or ""
            category = row.get("category") or ""
            content = f"{name} {category}".strip()
            contents.append(content)

            metadata: Dict[str, Optional[str]] = {
                "pantry_item_id": str(row.get("id")) if row.get("id") is not None else None,
                "name": name or None,
                "category": category or None,
                "quantity": str(row.get("quantity"))
                if row.get("quantity") is not None
                else None,
                "unit": row.get("unit"),
                "expiry_date": (
                    format_iso_date(value=row.get("expiry_date"))
                    if row.get("expiry_date") is not None
                    else None
                ),
                "owner_id": str(row.get("owner_id"))
                if row.get("owner_id") is not None
                else None,
                "household_id": (
                    str(row.get("household_id"))
                    if row.get("household_id") is not None
                    else None
                ),
                "expiry_visible": row.get("expiry_visible"),
            }
            metadatas.append(metadata)

        embeddings_queued = 0
        try:
            # Generate embeddings for all contents in a single batch
            embeddings: List[List[float]] = await anyio.to_thread.run_sync(
                lambda: self.embeddings_client.embed_documents(contents)
            )

            # Prepare payloads for pantry_embeddings upsert
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

        # Build per-item bulk results
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
        Gets all pantry items for the specified household and user.
        """
        try:
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch pantry items",
            ) from exc

        return response.data or []

    async def get_household_pantry_items(self, household_id: UUID) -> List[PantryItem]:
        """
        Gets all pantry items for the specified household.
        """
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .select("*")
                    .eq("household_id", str(household_id))
                    .execute()
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch household pantry items",
            ) from exc

        return response.data or []