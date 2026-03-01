"""User schemas - never expose hashed_password."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserResponse(BaseModel):
    """User response schema - no hashed_password."""

    id: UUID
    tenant_id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
