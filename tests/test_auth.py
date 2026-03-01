"""Tests for authentication - registration, login, JWT."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient) -> None:
    """Test user registration creates tenant and owner."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "new@test.com",
            "password": "securepass123",
            "tenant_name": "NewTenant",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_tenant(client: AsyncClient) -> None:
    """Test registration fails for duplicate tenant name."""
    await client.post(
        "/auth/register",
        json={
            "email": "first@test.com",
            "password": "pass123",
            "tenant_name": "DupTenant",
        },
    )
    resp = await client.post(
        "/auth/register",
        json={
            "email": "second@test.com",
            "password": "pass123",
            "tenant_name": "DupTenant",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient, auth_token: str) -> None:
    """Test login returns JWT."""
    resp = await client.post(
        "/auth/login",
        json={"email": "auth@test.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """Test login fails for invalid password."""
    await client.post(
        "/auth/register",
        json={
            "email": "login@test.com",
            "password": "pass123",
            "tenant_name": "LoginTenant",
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "login@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_users_me_requires_auth(client: AsyncClient) -> None:
    """Test /users/me returns 401 without token."""
    resp = await client.get("/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_users_me_with_token(client: AsyncClient, auth_headers: dict) -> None:
    """Test /users/me returns user with valid token."""
    resp = await client.get("/users/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "auth@test.com"
