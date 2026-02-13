from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

class HouseholdBase(BaseModel):
    """Base household model"""
    name: str = Field(..., min_length=1, max_length=100)

class HouseholdCreate(HouseholdBase):
    """Model for creating a household."""
    is_personal: bool = False


HouseholdCreateRequest = HouseholdCreate  # Alias for router request body

class HouseholdUpdate(BaseModel):
    """Model for updating household"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)

class HouseholdResponse(HouseholdBase):
    """Model for household response"""
    id: UUID
    invite_code: str
    is_personal: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True

class HouseholdMemberBase(BaseModel):
    """Base household member model"""
    user_id: UUID
    household_id: UUID

class HouseholdMemberResponse(HouseholdMemberBase):
    """Model for household member response"""
    id: UUID
    joined_at: datetime
    user_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class HouseholdWithMembers(HouseholdResponse):
    """Household with member list"""
    members: List[HouseholdMemberResponse] = Field(default_factory=list)
    member_count: int = 0

class HouseholdJoinRequest(BaseModel):
    """Model for joining a household via invite code"""
    invite_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("invite_code")
    def validate_invite_code(cls, value: str) -> str:
        """Ensure invite code is uppercase alphanumeric"""
        normalized_value = value.upper().strip()
        if not normalized_value.isalnum():
            raise ValueError("Invite code must be alphanumeric")
        return normalized_value

class HouseholdJoinResponse(BaseModel):
    """Response after joining a household by invite code."""
    household: HouseholdResponse
    items_moved: int = 0


class HouseholdLeaveResponse(BaseModel):
    """Response when leaving household"""
    message: str
    items_deleted: int = 0
    new_household_id: Optional[UUID] = None
    new_household_name: Optional[str] = None


class HouseholdConvertToJoinableRequest(BaseModel):
    """Optional body when converting personal household to joinable (shared)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)