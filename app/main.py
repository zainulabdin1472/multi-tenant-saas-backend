"""TeamFlow - Multi-tenant SaaS Backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.core.logging_middleware import LoggingMiddleware
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.tenants import router as tenants_router
from app.api.users import router as users_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}") from e
    yield
    await engine.dispose()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("teamflow")
logger.setLevel(logging.INFO)

app = FastAPI(
    title="TeamFlow API",
    description="Multi-tenant SaaS Backend - Production Ready",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(projects_router)
app.include_router(tasks_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
