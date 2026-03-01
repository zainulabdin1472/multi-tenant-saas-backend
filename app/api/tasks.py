"""Tasks API - tenant-scoped, RBAC enforced."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task import TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

_TASK_SORT_COLUMNS = {"created_at", "updated_at", "title", "status"}


@router.get(
    "/",
    response_model=PaginatedResponse[TaskRead],
)
async def list_all_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
    search: str | None = Query(None, description="Search by title"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
) -> PaginatedResponse[TaskRead]:
    """List all tasks for tenant across projects. Supports search, filter, pagination."""
    stmt = select(Task).where(
        Task.tenant_id == current_tenant.id,
        Task.is_deleted.is_(False),
    )
    count_stmt = select(func.count(Task.id)).where(
        Task.tenant_id == current_tenant.id,
        Task.is_deleted.is_(False),
    )
    if search:
        stmt = stmt.where(Task.title.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Task.title.ilike(f"%{search}%"))
    if status_filter:
        try:
            task_status = TaskStatus(status_filter)
            stmt = stmt.where(Task.status == task_status)
            count_stmt = count_stmt.where(Task.status == task_status)
        except ValueError:
            pass
    sort_col = sort if sort in _TASK_SORT_COLUMNS else "created_at"
    sort_attr = getattr(Task, sort_col, Task.created_at)
    stmt = stmt.order_by(sort_attr.desc() if order == "desc" else sort_attr.asc())
    stmt = stmt.offset(skip).limit(limit)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return PaginatedResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[
            TaskRead(
                id=t.id,
                project_id=t.project_id,
                tenant_id=t.tenant_id,
                title=t.title,
                description=t.description,
                status=t.status.value,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ],
    )


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> TaskRead:
    """Get task detail. Tenant isolation enforced. Excludes soft-deleted."""
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_tenant.id,
            Task.is_deleted.is_(False),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        tenant_id=task.tenant_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> TaskRead:
    """Update task. Members can update."""
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_tenant.id,
            Task.is_deleted.is_(False),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.status is not None:
        task.status = TaskStatus(data.status.value)
    await db.flush()
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        tenant_id=task.tenant_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> None:
    """Soft delete task."""
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_tenant.id,
            Task.is_deleted.is_(False),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    task.is_deleted = True
    await db.flush()
