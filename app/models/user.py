from __future__ import annotations

from pydantic import BaseModel, Field


class UserPreferencesBase(BaseModel):
    """
    Base model for user preferences.
    
    Defines all preference fields with their default values and validation constraints.
    """

    expiry_alerts_enabled: bool = Field(
        default=True, description="Enable expiry date alerts for pantry items"
    )
    pantry_check_enabled: bool = Field(
        default=True, description="Enable periodic pantry check reminders"
    )
    pantry_check_frequency_days: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Frequency in days for pantry check reminders (1-30 days)",
    )
    shopping_list_reminder_enabled: bool = Field(
        default=True, description="Enable shopping list reminder notifications"
    )
    shopping_list_reminder_days: int = Field(
        default=2,
        ge=1,
        le=14,
        description="Days before shopping list reminder (1-14 days)",
    )


class UserPreferences(UserPreferencesBase):
    """
    Model for user preferences response.
    
    Used when returning user preferences from the API.
    """

    pass


class UserPreferencesUpdate(BaseModel):
    """
    Model for updating user preferences.
    
    All fields are optional to allow partial updates.
    Only provided fields will be updated.
    """

    expiry_alerts_enabled: bool | None = Field(
        default=None, description="Enable expiry date alerts for pantry items"
    )
    pantry_check_enabled: bool | None = Field(
        default=None, description="Enable periodic pantry check reminders"
    )
    pantry_check_frequency_days: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="Frequency in days for pantry check reminders (1-30 days)",
    )
    shopping_list_reminder_enabled: bool | None = Field(
        default=None, description="Enable shopping list reminder notifications"
    )
    shopping_list_reminder_days: int | None = Field(
        default=None,
        ge=1,
        le=14,
        description="Days before shopping list reminder (1-14 days)",
    )


__all__ = [
    "UserPreferencesBase",
    "UserPreferences",
    "UserPreferencesUpdate",
]