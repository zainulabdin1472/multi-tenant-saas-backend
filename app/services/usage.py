"""Usage metering service."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.models.task import Task
from app.models.usage_event import UsageEvent


async def log_usage_event(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    usage_count: int = 1,
) -> UsageEvent:
    """Log a usage event for the tenant."""
    event = UsageEvent(
        tenant_id=tenant_id,
        feature_name=feature_name,
        usage_count=usage_count,
    )
    db.add(event)
    await db.flush()
    return event


async def count_tenant_projects(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Count non-deleted projects for tenant."""
    result = await db.execute(
        select(func.count(Project.id)).where(
            Project.tenant_id == tenant_id,
            Project.is_deleted.is_(False),
        )
    )
    return result.scalar() or 0


async def count_project_tasks(db: AsyncSession, project_id: uuid.UUID) -> int:
    """Count non-deleted tasks for a project."""
    result = await db.execute(
        select(func.count(Task.id)).where(
            Task.project_id == project_id,
            Task.is_deleted.is_(False),
        )
    )
    return result.scalar() or 0
