from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel


def to_public_dict(
    *,
    model: BaseModel,
    exclude_none: bool = True,
    exclude_unset: bool = True,
) -> dict[str, Any]:
    return model.model_dump(exclude_none=exclude_none, exclude_unset=exclude_unset)


def wrap_response(*, data: Any, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"data": data}
    if meta is not None:
        response["meta"] = dict(meta)
    return response


__all__ = [
    "to_public_dict",
    "wrap_response",
]
