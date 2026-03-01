"""Project schemas - tenant_id never from client."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Schema for project creation - no tenant_id."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class ProjectRead(BaseModel):
    """Project response schema."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    """Schema for project update - no tenant_id."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
