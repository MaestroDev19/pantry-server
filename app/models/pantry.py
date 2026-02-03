from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from uuid import UUID
from enum import Enum

# ---------------------------
# Enum definitions for pantry
# ---------------------------

class CategoryEnum(str, Enum):
    """
    Categories for classifying pantry items. Used to group food/products for filtering and statistics.
    """
    DAIRY = "Dairy"                     # e.g., milk, cheese, yogurt
    PRODUCE = "Produce"                 # e.g., fruits, vegetables
    MEAT_SEAFOOD = "Meat & Seafood"     # e.g., chicken, beef, fish
    GRAINS_PASTA = "Grains & Pasta"     # e.g., rice, pasta, bread
    CANNED_GOODS = "Canned Goods"       # e.g., canned beans, soup
    FROZEN = "Frozen"                   # e.g., frozen vegetables, ice cream
    SNACKS = "Snacks"                   # e.g., chips, crackers
    BEVERAGES = "Beverages"             # e.g., juice, soda
    CONDIMENTS_OILS = "Condiments & Oils" # e.g., ketchup, olive oil
    BAKING = "Baking"                   # e.g., flour, baking powder
    OTHER = "Other"                     # Any item not covered above

class UnitEnum(str, Enum):
    """
    Predefined units for pantry item quantities, covering most common measurement types.
    """
    # Weight Units
    KG = "kg"       # kilograms
    G = "g"         # grams
    MG = "mg"       # milligrams
    LB = "lb"       # pounds
    OZ = "oz"       # ounces

    # Volume Units
    L = "L"         # liters
    ML = "mL"       # milliliters
    GAL = "gal"     # gallons
    CUP = "cup"     # cups
    TBSP = "tbsp"   # tablespoons
    TSP = "tsp"     # teaspoons

    # Count Units
    PIECES = "pieces"   # for countable things, e.g. eggs
    ITEMS = "items"     # (generic count unit)

    # Packaging Units
    CAN = "can"
    BOTTLE = "bottle"
    BOX = "box"
    BAG = "bag"
    PACK = "pack"

class ExpiryStatus(str, Enum):
    """
    Classification of an item's freshness or expiry state based on the expiry date.
    """
    GOOD = "good"             # Expiry > 7 days from now
    EXPIRING_SOON = "expiring_soon"   # Expiry within 3-7 days
    EXPIRED = "expired"               # Expiry < 3 days or already past
    NO_DATE = "no_date"               # No expiry date specified

# ------------------------------------
# Main pantry item modeling classes
# ------------------------------------

class PantryItemBase(BaseModel):
    """
    Base model for pantry item creation, update, and response.
    Most common fields for describing a pantry item.
    """
    name: str = Field(..., min_length=1, max_length=100)      # Display name for the item (e.g., "Carrots")
    category: CategoryEnum                                     # Category for grouping/filtering
    quantity: float = Field(default=1.0, gt=0, le=10000)       # How much/many of this item (must be >0)
    unit: Optional[UnitEnum] = None                            # Unit for quantity, optional (can be items/pieces/etc.)
    expiry_date: Optional[date] = None                         # Expiry date, optional
    expiry_visible: bool = True                                # If false, hide expiry in UI (for non-perishables)

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        """
        Ensure the item name is trimmed of whitespace and title-cased (e.g., 'carrots' -> 'Carrots'). 
        """
        return value.strip().title()

    @field_validator("expiry_date")
    def validate_expiry_date(cls, value: Optional[date]) -> Optional[date]:
        """
        Expiry date may not be set more than 1 year in the past, or it's invalid.
        This avoids errors/input mistakes.
        """
        if value and value < date.today().replace(year=date.today().year - 1):
            raise ValueError("Expiry date cannot be more than 1 year in the past")
        return value

class PantryItemCreate(PantryItemBase):
    """
    Payload for creating a new pantry item. Inherits all fields from PantryItemBase.
    """
    pass

class PantryItemUpsert(PantryItemBase):
    """
    Payload for upserting (insert or update) a pantry item. Useful for bulk actions or deduplication. Inherits PantryItemBase.
    """
    pass

class PantryItemUpdate(BaseModel):
    """
    Payload for updating fields of a pantry item. All fields optional;
    only those supplied will be changed.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[CategoryEnum] = None
    quantity: Optional[float] = Field(None, gt=0, le=10000)
    unit: Optional[UnitEnum] = None
    expiry_date: Optional[date] = None
    expiry_visible: Optional[bool] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        """
        If the name is being updated, trim and title-case it as with creation.
        """
        if value is None:
            return value
        return value.strip().title()

class PantryItemResponse(PantryItemBase):
    """
    Full response for a pantry item, returned from API. Includes immutable database and computed fields.
    Inherits PantryItemBase for shared fields.
    """
    id: UUID                           # Unique item identifier (from database)
    owner_id: UUID                     # UUID of the user who added/owns the item
    household_id: UUID                 # UUID of the household the item belongs to
    created_at: datetime               # When the item was added
    updated_at: datetime               # Last update time

    # Computed fields, useful for UI indication and filtering.
    expiry_status: Optional[ExpiryStatus] = None       # Computed from expiry_date and today's date
    days_until_expiry: Optional[int] = None            # Number of days left, for sorting/warning popups
    is_mine: bool = False                              # Indicates if this item belongs to the requesting user

    class Config:
        from_attributes = True   # Enable ORM mode for easy DB-to-model mapping
        use_enum_values = True   # Auto-convert enums to their value when serializing to JSON

class PantryItemWithOwner(PantryItemResponse):
    """
    Extends PantryItemResponse to include owner email/name, useful for shared households.
    """
    owner_email: Optional[str] = None  # Email of item creator/owner
    owner_name: Optional[str] = None   # Display name of item owner

class PantryItemUpsertResponse(BaseModel):
    """
    API response after an upsert action.
    Indicates if the row was newly created or changed, by how much,
    and whether an embedding was generated (for search).
    """
    id: UUID                          # Main Pantry Item ID
    is_new: bool                      # If this was a new (not pre-existing) row
    old_quantity: float               # Quantity before upsert (0 if new)
    new_quantity: float               # Quantity after upsert
    message: str                      # Human-readable result message
    embedding_generated: bool         # Whether an AI embedding was created/updated

class PantryItemMarkUsed(BaseModel):
    """
    Payload to notify that some of an item was used/consumed.
    For tracking consumption and updating available quantity.
    """
    quantity_used: Optional[float] = Field(None, gt=0) # Amount used (optional; required if marking partial use)

class PantrySummary(BaseModel):
    """
    Aggregated info for all pantry items - used in dashboards/UIs.
    Helps users quickly scan status and spot soon-to-expire items.
    """
    total_items: int = 0                # Grand total of all items (across categories/owners)
    my_items: int = 0                   # Count belonging to current user (if filtering by household)
    good_count: int = 0                 # Items with expiry status GOOD
    expiring_soon_count: int = 0        # Items with expiry status EXPIRING_SOON
    expired_count: int = 0              # Items with expiry status EXPIRED
    categories: dict = Field(default_factory=dict) # Mapping of counts per CategoryEnum

class PantryFilterParams(BaseModel):
    """
    Model for parameters with which you may filter pantry items via API.
    Used in list/search endpoints.
    """
    owner_id: Optional[UUID] = None                                # If given, only show items owned by this user
    category: Optional[CategoryEnum] = None                        # Filter by category if specified
    expiry_status: Optional[ExpiryStatus] = None                   # Filter for only good/expired/expiring soon items
    search: Optional[str] = Field(None, max_length=100)            # Text search/substring on name
    sort_by: str = Field(default="expiry_date", pattern="^(name|category|expiry_date|created_at)$") # Column to sort by
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")                                  # "asc" or "desc"
    limit: int = Field(default=50, ge=1, le=100)                   # Max result count (pagination)
    offset: int = Field(default=0, ge=0)                           # Offset for pagination, 0-based