"""Pytest fixtures for TeamFlow tests."""

import os
import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import get_password_hash


if "TEST_DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
else:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
        poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden DB session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    """Create test tenant."""
    tenant_obj = Tenant(name="TestTenant", subscription_plan="free")
    db_session.add(tenant_obj)
    await db_session.flush()
    await db_session.commit()
    return tenant_obj


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, tenant: Tenant) -> User:
    """Create test owner user."""
    user_obj = User(
        tenant_id=tenant.id,
        email="owner@test.com",
        hashed_password=get_password_hash("password123"),
        role="owner",
    )
    db_session.add(user_obj)
    await db_session.flush()
    await db_session.commit()
    return user_obj


@pytest_asyncio.fixture
async def member_user(db_session: AsyncSession, tenant: Tenant) -> User:
    """Create test member user."""
    user_obj = User(
        tenant_id=tenant.id,
        email="member@test.com",
        hashed_password=get_password_hash("password123"),
        role="member",
    )
    db_session.add(user_obj)
    await db_session.flush()
    await db_session.commit()
    return user_obj


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Register and login to get auth token."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "auth@test.com",
            "password": "password123",
            "tenant_name": "AuthTenant",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict[str, str]:
    """Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}
