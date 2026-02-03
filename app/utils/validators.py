from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    value: Any | None = None
    error_message: str | None = None


def normalize_title_case(*, value: str) -> str:
    return value.strip().title()


def normalize_trim(*, value: str) -> str:
    return value.strip()


def validate_in_set(*, value: str, allowed_values: set[str], field_name: str) -> ValidationResult:
    normalized_value = value.strip()
    if normalized_value not in allowed_values:
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid {field_name}",
        )
    return ValidationResult(is_valid=True, value=normalized_value)


__all__ = [
    "ValidationResult",
    "normalize_title_case",
    "normalize_trim",
    "validate_in_set",
]
