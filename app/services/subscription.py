"""Subscription plan enforcement service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.subscription import get_plan
from app.models.tenant import Tenant
from app.services.usage import count_project_tasks, count_tenant_projects


async def check_project_limit(
    db: AsyncSession, tenant: Tenant
) -> None:
    """Raise HTTPException if tenant has reached project limit."""
    plan = get_plan(tenant.subscription_plan)
    if plan.project_limit is None:
        return
    count = await count_tenant_projects(db, tenant.id)
    if count >= plan.project_limit:
        raise ValueError(f"Project limit reached ({plan.project_limit})")


async def check_task_limit(
    db: AsyncSession, tenant: Tenant, project_id: uuid.UUID
) -> None:
    """Raise ValueError if project has reached task limit."""
    plan = get_plan(tenant.subscription_plan)
    if plan.task_limit_per_project is None:
        return
    count = await count_project_tasks(db, project_id)
    if count >= plan.task_limit_per_project:
        raise ValueError(
            f"Task limit per project reached ({plan.task_limit_per_project})"
        )
