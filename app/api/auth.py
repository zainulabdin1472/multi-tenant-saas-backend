"""Authentication API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.services.usage import log_usage_event
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import RegisterRequest, Token, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(
    data: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Create new tenant and owner user. Returns JWT."""
    result = await db.execute(
        select(Tenant).where(Tenant.name == data.tenant_name)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant name already exists",
        )
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    tenant = Tenant(name=data.tenant_name, subscription_plan="free")
    db.add(tenant)
    await db.flush()
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role="owner",
    )
    db.add(user)
    await db.flush()
    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(tenant.id),
        role=user.role,
    )
    return Token(access_token=token, token_type="bearer")


@router.post("/login", response_model=Token)
async def login(
    data: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate user. Returns JWT including tenant_id."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    result_tenant = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result_tenant.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant association missing",
        )
    await log_usage_event(db, user.tenant_id, "user_login")
    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
    )
    return Token(access_token=token, token_type="bearer")
