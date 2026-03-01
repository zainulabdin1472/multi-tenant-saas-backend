"""Projects API - tenant-scoped, RBAC enforced."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.auth import (
    get_current_tenant,
    get_current_user,
    require_role,
)
from app.db.session import get_db
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.task import TaskCreate, TaskRead
from app.services.subscription import check_project_limit, check_task_limit
from app.services.usage import log_usage_event

router = APIRouter(prefix="/projects", tags=["projects"])

_PROJECT_SORT_COLUMNS = {"created_at", "updated_at", "name"}
_TASK_SORT_COLUMNS = {"created_at", "updated_at", "title", "status"}


@router.post("/{project_id}/tasks", response_model=TaskRead)
async def create_task(
    project_id: uuid.UUID,
    data: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> TaskRead:
    """Create task in project. Members can create. Enforces task limit per project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_tenant.id,
            Project.is_deleted.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    try:
        await check_task_limit(db, current_tenant, project_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    task = Task(
        project_id=project_id,
        tenant_id=current_tenant.id,
        title=data.title,
        description=data.description,
        status=TaskStatus(data.status.value),
    )
    db.add(task)
    await log_usage_event(db, current_tenant.id, "task_created")
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


@router.get(
    "/{project_id}/tasks",
    response_model=PaginatedResponse[TaskRead],
)
async def list_tasks(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
    search: str | None = Query(None, description="Search by title"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
) -> PaginatedResponse[TaskRead]:
    """List tasks for project. Tenant isolation enforced. Supports search, filter, pagination."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_tenant.id,
            Project.is_deleted.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    stmt = select(Task).where(
        Task.project_id == project_id,
        Task.tenant_id == current_tenant.id,
        Task.is_deleted.is_(False),
    )
    count_stmt = select(func.count(Task.id)).where(
        Task.project_id == project_id,
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


@router.post("/", response_model=ProjectRead)
async def create_project(
    data: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, require_role("owner", "admin")],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> ProjectRead:
    """Create project. RBAC: owner/admin only. Enforces subscription limit."""
    try:
        await check_project_limit(db, current_tenant)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    project = Project(
        tenant_id=current_tenant.id,
        name=data.name,
        description=data.description,
    )
    db.add(project)
    await log_usage_event(db, current_tenant.id, "project_created")
    await db.flush()
    return ProjectRead.model_validate(project)


@router.get(
    "/",
    response_model=PaginatedResponse[ProjectRead],
)
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
    search: str | None = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
) -> PaginatedResponse[ProjectRead]:
    """List projects for current tenant. Supports search, pagination, sorting."""
    stmt = select(Project).where(
        Project.tenant_id == current_tenant.id,
        Project.is_deleted.is_(False),
    )
    count_stmt = select(func.count(Project.id)).where(
        Project.tenant_id == current_tenant.id,
        Project.is_deleted.is_(False),
    )
    if search:
        stmt = stmt.where(Project.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Project.name.ilike(f"%{search}%"))
    sort_col = sort if sort in _PROJECT_SORT_COLUMNS else "created_at"
    sort_attr = getattr(Project, sort_col, Project.created_at)
    stmt = stmt.order_by(sort_attr.desc() if order == "desc" else sort_attr.asc())
    stmt = stmt.offset(skip).limit(limit)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return PaginatedResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[ProjectRead.model_validate(p) for p in projects],
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> ProjectRead:
    """Get project detail. Tenant isolation enforced. Excludes soft-deleted."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_tenant.id,
            Project.is_deleted.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return ProjectRead.model_validate(project)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, require_role("owner", "admin")],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> ProjectRead:
    """Update project. RBAC: owner/admin only."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_tenant.id,
            Project.is_deleted.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    await db.flush()
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, require_role("owner", "admin")],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> None:
    """Soft delete project. RBAC: owner/admin only."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == current_tenant.id,
            Project.is_deleted.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    project.is_deleted = True
    await db.flush()
