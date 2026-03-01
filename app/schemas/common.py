"""Common schemas - pagination."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response with total count."""

    total: int
    skip: int
    limit: int
    items: list[T]
