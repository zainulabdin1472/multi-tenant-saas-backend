"""Usage event schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UsageEventRead(BaseModel):
    """Usage event response schema."""

    id: UUID
    tenant_id: UUID
    feature_name: str
    usage_count: int
    timestamp: datetime

    model_config = {"from_attributes": True}
