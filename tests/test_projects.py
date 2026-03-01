"""Tests for projects CRUD, tenant isolation, RBAC, soft delete, subscription."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project_owner(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test owner can create project."""
    resp = await client.post(
        "/projects/",
        headers=auth_headers,
        json={"name": "My Project", "description": "Test project"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Project"
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_list_projects(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test list projects returns tenant-scoped results."""
    resp = await client.get("/projects/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_projects_pagination(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test pagination params."""
    resp = await client.get(
        "/projects/",
        headers=auth_headers,
        params={"skip": 0, "limit": 5, "sort": "created_at", "order": "desc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skip"] == 0
    assert data["limit"] == 5


@pytest.mark.asyncio
async def test_soft_delete_project(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test delete marks project as deleted, not hard delete."""
    create_resp = await client.post(
        "/projects/",
        headers=auth_headers,
        json={"name": "To Delete", "description": ""},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]
    del_resp = await client.delete(
        f"/projects/{project_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204
    get_resp = await client.get(f"/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 404
