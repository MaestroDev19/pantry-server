from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime
from utils.date_time_styling import format_iso_datetime, format_iso_date, format_display_date
import anyio  # Library providing asynchronous concurrency primitives and utilities for running sync code in threads
from fastapi import HTTPException, status  # Used to handle HTTP errors and response codes
from supabase import Client  # Supabase client for Postgres operations

from ai.vector_store import get_vector_store  # Factory to obtain a vector store instance (e.g., for semantic search)
from models.pantry import (
    PantryItem,
    PantryItemCreate,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
    BulkUpsertResult,
)  # Collection of Pydantic models for data validation and serialization for pantry operations
from utils.embedding import embeddings_client  # Embedding utility for generating vector representations of pantry items


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
        # --- Verify user is in the household; enforce RLS before making data changes
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
        # If user is not in the household, abort with HTTP 403 Forbidden to prevent unauthorized inserts
        if not getattr(membership_response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the specified household",
            )

        # --- Build dictionary for upserting pantry item with current creation/updated dates and related fields
        data = pantry_item.model_dump()
        data["household_id"] = str(household_id)  # Always tie item to a household
        data["owner_id"] = str(user_id)           # Always record owner
        data["created_at"] = format_iso_datetime(value=datetime.now())    # Creation timestamp
        data["updated_at"] = format_iso_datetime(value=datetime.now())    # Last update timestamp
        data["expiry_date"] = format_iso_date(value=data["expiry_date"]) if data["expiry_date"] else None  # Normalize date or null if not set

        try:
            # Upsert (insert or update) into the pantry_items table.
            # This operation must select and return the whole row for further processing.
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .upsert(data)
                        .select("*")
                        .execute()
                )
            )
        except Exception as exc:
            # If a database/network error occurs, respond with 502 Bad Gateway.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create pantry item",
            ) from exc

        # If upsert fails to return a valid data response, return an internal error; item creation failed.
        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pantry item was not created",
            )

        # Grab the item dictionary (row) returned from database upsert. We expect exactly one row.
        row = response.data[0]
        print(row)  # Useful debug print

        # --- Try to generate semantic embedding and insert into 'pantry_embeddings' table
        embedding_generated = False  # Track embedding status so it can be reported to the UI
        try:
            # Compose the textual content to embed, typically item name and category.
            name = row.get("name") or ""
            category = row.get("category") or ""
            content = f"{name} {category}".strip()  # E.g., "Milk Dairy"

            # Metadata for the embedding entry, mirroring the DB trigger logic.
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

            # Generate dense embedding vector with the embedding client (blocking, so run in thread)
            embeddings: List[List[float]] = await anyio.to_thread.run_sync(
                lambda: self.embeddings_client.embed_documents([content])
            )
            # Pick the embedding for this one item, or None if failed
            embedding_vector = embeddings[0] if embeddings else None

            if embedding_vector is not None:
                # Insert or update the embedding record for this item, with current creation time.
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
                embedding_generated = True  # Mark success for response payload
        except Exception:
            # On any failure in embedding, just record status as false; do not abort entire item creation
            embedding_generated = False

        # Compose and return the response, reflecting upsert result and embedding status
        return PantryItemUpsertResponse(
            id=row["id"],                   # Assigned or detected item id
            is_new=True,                    # This interface is only for new inserts, always true
            old_quantity=0,                 # There was no previous quantity for a new insert
            new_quantity=float(row.get("quantity") or 0),  # The quantity provided, coerced to float
            message="Pantry item added successfully",      # UX message for client
            embedding_generated=embedding_generated,       # Did we successfully store an embedding?
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
        # ----- 1. Membership Check: Only allow bulk upsert if user is in household.
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

        # ----- 2. Prepare Bulk Upsert Data: Augment each item with core fields
        rows_to_upsert: List[Dict[str, object]] = []  # Will contain a dict per row to insert
        for item in pantry_items:
            data = item.model_dump()
            data["household_id"] = str(household_id)
            data["owner_id"] = str(user_id)
            data["created_at"] = format_iso_datetime(value=datetime.now())
            data["updated_at"] = format_iso_datetime(value=datetime.now())
            data["expiry_date"] = format_iso_date(value=data["expiry_date"]) if data["expiry_date"] else None
            rows_to_upsert.append(data)

        # ----- 3. Perform Bulk Upsert in Pantry Table
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                        .upsert(rows_to_upsert)
                        .select("*")
                        .execute()
                )
            )
        except Exception as exc:
            # Return 502 if there was any sort of database/network fault
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create pantry items",
            ) from exc

        # If the upsert was not successful (e.g. returns no data), treat as an error.
        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pantry items were not created",
            )

        created_rows: List[Dict] = list(response.data)  # All upserted rows; each a dict

        # ----- 4. Prepare Embedding Inputs: For each row, build the text to embed and associated metadata.
        contents: List[str] = []  # Text like "Milk Dairy" for each item
        metadatas: List[Dict[str, Optional[str]]] = []
        for row in created_rows:
            name = row.get("name") or ""
            category = row.get("category") or ""
            content = f"{name} {category}".strip()
            contents.append(content)

            # Compose matching metadata as in the single upsert
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

        # ----- 5. Generate All Embeddings in a Batch and Upsert Embedding Records
        embeddings_queued = 0  # Keep count of successful embedding records
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
                    continue  # skip if embedding empty/faulty
                embedding_rows.append(
                    {
                        "pantry_item_id": row["id"],
                        "content": content,
                        "metadata": metadata,
                        "embedding": embedding_vector,
                    }
                )

            # If we generated any valid embeddings, upsert them in a separate call
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
            # Fail quietly with zero embeddings; do not fail the whole batch on embedding error.
            embeddings_queued = 0

        # ----- 6. Compile BulkUpsertResult for each created item (all treated as new in this API)
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

        # Tally summary counts for the response payload.
        total_requested = len(pantry_items)
        successful = len(bulk_results)
        failed = total_requested - successful

        # Return a bulk create response containing results and summary
        return PantryItemsBulkCreateResponse(
            total_requested=total_requested,
            successful=successful,
            failed=failed,
            new_items=successful,  # Bulk API only used for creation; no updates
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
            # Database error: respond with HTTP 502 (gateway error)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch pantry items",
            ) from exc

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
            # In case of database/query failure, signal 502 error to client.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch household pantry items",
            ) from exc

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
            # Any error during update, bubble up to client as 502 error.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to update pantry item",
            ) from exc

        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pantry item not found or not owned by user",
            )

        row = response.data[0]

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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to delete pantry item",
            ) from exc

        if not getattr(response, "data", None):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pantry item not found or not owned by user",
            )

        row = response.data[0]

        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=False,
            old_quantity=float(row.get("quantity") or 0),
            new_quantity=0.0,
            message="Pantry item deleted successfully",
            embedding_generated=False,
        )