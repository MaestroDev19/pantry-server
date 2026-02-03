from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from enum import Enum

class ShoppingListItemBase(BaseModel):
    """Base shopping list item"""
    name: str = Field(..., min_length=1, max_length=100)
    quantity: float = Field(default=1.0, gt=0, le=1000)
    unit: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=200)

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        return value.strip().title()

class ShoppingListItemCreate(ShoppingListItemBase):
    """Model for creating shopping list item"""
    pass

class ShoppingListItemUpdate(BaseModel):
    """Model for updating shopping list item"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    quantity: Optional[float] = Field(None, gt=0, le=1000)
    unit: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=200)
    purchased: Optional[bool] = None

class ShoppingListItem(ShoppingListItemBase):
    """Shopping list item with metadata"""
    purchased: bool = False
    purchased_at: Optional[datetime] = None
    reason: Optional[str] = None  # "running_low", "expiring", "recipe", "manual"
    estimated_price: Optional[float] = None

class ShoppingListBase(BaseModel):
    """Base shopping list model"""
    items: List[ShoppingListItem] = Field(default_factory=list)

class ShoppingListResponse(ShoppingListBase):
    """Model for shopping list response"""
    id: UUID
    user_id: UUID
    generated_at: datetime
    updated_at: datetime
    
    # Computed fields
    total_items: int = 0
    purchased_items: int = 0
    pending_items: int = 0
    
    class Config:
        from_attributes = True

class ShoppingListGenerateRequest(BaseModel):
    """Request to generate shopping list"""
    include_low_stock: bool = True
    include_expiring: bool = True
    include_staples: bool = True
    max_items: int = Field(default=20, ge=5, le=50)

class ShoppingListMarkPurchasedRequest(BaseModel):
    """Request to mark items as purchased"""
    item_indices: List[int] = Field(..., min_items=1)
    add_to_pantry: bool = True

class ShoppingListMarkPurchasedResponse(BaseModel):
    """Response after marking items as purchased"""
    purchased_count: int
    added_to_pantry_count: int
    pantry_item_ids: List[UUID] = Field(default_factory=list)
    message: str

class ShoppingListExportFormat(str, Enum):
    """Export format options"""
    TEXT = "text"
    JSON = "json"
    CSV = "csv"

class ShoppingListExportRequest(BaseModel):
    """Request to export shopping list"""
    format: ShoppingListExportFormat = ShoppingListExportFormat.TEXT
    include_purchased: bool = False