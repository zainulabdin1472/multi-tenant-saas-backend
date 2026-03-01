"""Tenants API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.tenant import TenantResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantResponse)
async def get_tenant_me(
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> TenantResponse:
    """Return tenant info for current user."""
    return TenantResponse.model_validate(current_tenant)
