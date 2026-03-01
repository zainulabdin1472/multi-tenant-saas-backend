"""Tenant schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TenantResponse(BaseModel):
    """Tenant response schema."""

    id: UUID
    name: str
    subscription_plan: str
    created_at: datetime

    model_config = {"from_attributes": True}
