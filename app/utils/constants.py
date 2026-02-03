from __future__ import annotations

from typing import Final

from app.models.pantry import CategoryEnum, UnitEnum

# NOTE: keep this module dependency-light; it should only expose constants and
# derived constant values (no I/O, no environment access).

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200

CATEGORY_VALUES: Final[tuple[str, ...]] = tuple(category.value for category in CategoryEnum)
UNIT_VALUES: Final[tuple[str, ...]] = tuple(unit.value for unit in UnitEnum)

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "CATEGORY_VALUES",
    "UNIT_VALUES",
]
