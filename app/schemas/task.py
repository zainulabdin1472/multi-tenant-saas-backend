"""Task schemas - tenant_id never from client."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Task status enum for API."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskCreate(BaseModel):
    """Schema for task creation - no tenant_id."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatusEnum = TaskStatusEnum.TODO


class TaskRead(BaseModel):
    """Task response schema."""

    id: UUID
    project_id: UUID
    tenant_id: UUID
    title: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    """Schema for task update - no tenant_id."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatusEnum | None = None
