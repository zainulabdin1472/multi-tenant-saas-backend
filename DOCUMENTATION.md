# TeamFlow — Complete Project Documentation

This document provides an in-depth explanation of the TeamFlow multi-tenant SaaS backend for project and task management.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Directory Structure](#4-directory-structure)
5. [Data Models](#5-data-models)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [API Endpoints](#7-api-endpoints)
8. [Services & Business Logic](#8-services--business-logic)
9. [Configuration](#9-configuration)
10. [Database & Migrations](#10-database--migrations)
11. [Logging & Observability](#11-logging--observability)
12. [Testing](#12-testing)
13. [Deployment](#13-deployment)
14. [Security Considerations](#14-security-considerations)

---

## 1. Project Overview

### What is TeamFlow?

TeamFlow is a **production-ready multi-tenant SaaS backend** that enables organizations (tenants) to manage projects and tasks. Each organization has its own users, projects, and tasks, with strict isolation between tenants.

### Core Principles

- **Multi-tenancy**: Every user belongs to exactly one tenant. No global users.
- **Tenant ID from JWT only**: The client never sends `tenant_id`; it is always derived from the authenticated user's JWT.
- **Role-Based Access Control (RBAC)**: Roles (`owner`, `admin`, `member`) control what actions users can perform.
- **Soft deletes**: Projects and tasks are marked as deleted instead of being physically removed.
- **Subscription limits**: Free plans have limits; Pro and Enterprise are unlimited.

---

## 2. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client (Frontend / API Consumer)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP + Bearer JWT
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TeamFlow FastAPI Application                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Middleware: Logging, CORS                                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  API Routers: /auth, /users, /tenants, /projects, /tasks               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Dependencies: get_db, get_current_user, get_current_tenant, require_role │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Services: usage (metering), subscription (plan limits)                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ async SQLAlchemy
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PostgreSQL 15                                   │
│  Tables: tenants, users, projects, tasks, usage_events                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Tenant    │       │    User     │       │   Project   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │◄──────│ tenant_id   │       │ id (PK)     │
│ name        │       │ id (PK)     │       │ tenant_id ──┼──► Tenant
│ sub_plan    │       │ email       │       │ name        │
│ created_at  │       │ hashed_pwd  │       │ description │
└──────┬──────┘       │ role        │       │ is_deleted  │
       │              │ is_active   │       │ created_at  │
       │              │ created_at  │       │ updated_at  │
       │              └─────────────┘       └──────┬──────┘
       │                                          │
       │              ┌─────────────┐              │
       │              │    Task     │              │
       │              ├─────────────┤              │
       └─────────────►│ tenant_id ──┼──────────────┤
                      │ project_id ─┼──────────────┘
                      │ title       │
                      │ description │
                      │ status      │  (todo, in_progress, done)
                      │ is_deleted  │
                      │ created_at  │
                      │ updated_at  │
                      └─────────────┘

       ┌──────────────────────┐
       │    UsageEvent        │
       ├──────────────────────┤
       │ id (PK)              │
       │ tenant_id ───────────┼──► Tenant
       │ feature_name         │  (project_created, task_created, user_login)
       │ usage_count          │
       │ timestamp            │
       └──────────────────────┘
```

### Request Flow (Example: Create Project)

1. Client sends `POST /projects/` with `Authorization: Bearer <jwt>` and JSON body `{name, description}`.
2. `LoggingMiddleware` logs the request.
3. `get_current_user` extracts JWT, decodes it, loads `User` from DB, checks `is_active`.
4. `require_role("owner", "admin")` checks user role.
5. `get_current_tenant` loads `Tenant` from `current_user.tenant_id`.
6. `check_project_limit` verifies tenant hasn't exceeded subscription limit.
7. Project is created with `tenant_id` from JWT (never from client).
8. `log_usage_event` records `project_created`.
9. Response returned; middleware logs response status and duration.

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| API Framework | FastAPI | Async HTTP API, validation, OpenAPI docs |
| Server | Uvicorn | ASGI server |
| Database | PostgreSQL 15 | Persistent storage |
| ORM | SQLAlchemy 2.0 | Async ORM, declarative models |
| Driver | asyncpg | Async PostgreSQL driver |
| Migrations | Alembic | Schema versioning (async) |
| Auth | python-jose, passlib | JWT creation/validation, bcrypt hashing |
| Validation | Pydantic | Request/response schemas, settings |
| Testing | pytest, httpx, pytest-asyncio | Unit and integration tests |
| Container | Docker, Docker Compose | Deployment |

---

## 4. Directory Structure

```
teamflow/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, middleware, routes
│   │
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Pydantic settings (DATABASE_URL, SECRET_KEY, etc.)
│   │   ├── security.py         # Password hashing, JWT create/decode
│   │   ├── subscription.py     # Plan limits (free/pro/enterprise)
│   │   └── logging_middleware.py  # Request logging
│   │
│   ├── db/                     # Database layer
│   │   ├── base.py             # SQLAlchemy DeclarativeBase
│   │   └── session.py          # Async engine, session factory, get_db
│   │
│   ├── models/                 # SQLAlchemy models
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── usage_event.py
│   │   └── __init__.py
│   │
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── auth.py             # UserCreate, UserLogin, RegisterRequest, Token
│   │   ├── user.py             # UserResponse (no hashed_password)
│   │   ├── tenant.py           # TenantResponse
│   │   ├── project.py          # ProjectCreate, ProjectRead, ProjectUpdate
│   │   ├── task.py             # TaskCreate, TaskRead, TaskUpdate
│   │   ├── common.py           # PaginatedResponse[T]
│   │   └── usage.py            # UsageEventRead
│   │
│   ├── api/                    # API route handlers
│   │   ├── auth.py             # POST /auth/register, /auth/login
│   │   ├── users.py            # GET /users/me
│   │   ├── tenants.py          # GET /tenants/me
│   │   ├── projects.py         # CRUD projects + project-scoped tasks
│   │   └── tasks.py            # CRUD tasks (global list + by id)
│   │
│   ├── services/               # Business logic
│   │   ├── usage.py            # log_usage_event, count_tenant_projects, count_project_tasks
│   │   └── subscription.py     # check_project_limit, check_task_limit
│   │
│   └── dependencies/           # FastAPI dependencies
│       ├── __init__.py
│       └── auth.py             # get_current_user, get_current_tenant, require_role
│
├── alembic/
│   ├── env.py                  # Async Alembic env, metadata from models
│   ├── script.py.mako          # Migration template
│   ├── README
│   └── versions/               # Generated migrations
│
├── tests/
│   ├── test_auth.py            # Auth tests
│   ├── test_projects.py        # Project CRUD, soft delete, pagination
│   ├── test_tasks.py           # Task CRUD, soft delete
│   └── test_health.py          # Health endpoint
│
├── conftest.py                 # Pytest fixtures (client, auth_token, etc.)
├── pytest.ini                  # Pytest config
├── alembic.ini                 # Alembic config
├── Dockerfile                  # Backend container
├── docker-compose.yml          # Postgres + Backend
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not committed)
├── README.md                   # Quick start
└── DOCUMENTATION.md            # This file
```

---

## 5. Data Models

### Tenant (`app/models/tenant.py`)

Represents an organization/workspace.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| name | String(255), indexed | Organization name (unique per tenant) |
| subscription_plan | String(50) | `free`, `pro`, or `enterprise` |
| created_at | DateTime(timezone) | Creation timestamp |

**Relationships**: users, projects, tasks, usage_events (all cascade delete)

---

### User (`app/models/user.py`)

Belongs to a tenant. No global users.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| tenant_id | UUID (FK → tenants) | Foreign key, CASCADE delete |
| email | String(255), unique, indexed | User email (global uniqueness) |
| hashed_password | String(255) | bcrypt hash, never exposed in API |
| role | String(20) | `owner`, `admin`, or `member` |
| is_active | Boolean | Default true; inactive users cannot log in |
| created_at | DateTime(timezone) | Creation timestamp |

**Relationships**: tenant

---

### Project (`app/models/project.py`)

Belongs to a tenant. Soft-deletable.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| tenant_id | UUID (FK → tenants) | Foreign key |
| name | String(255), indexed | Project name |
| description | Text, nullable | Optional description |
| created_at | DateTime(timezone) | Creation timestamp |
| updated_at | DateTime(timezone) | Last update (auto-updated) |
| is_deleted | Boolean | Soft delete flag (default False) |

**Relationships**: tenant, tasks

---

### Task (`app/models/task.py`)

Belongs to a project and tenant. Soft-deletable.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| project_id | UUID (FK → projects) | Foreign key |
| tenant_id | UUID (FK → tenants) | Foreign key (denormalized for query efficiency) |
| title | String(255) | Task title |
| description | Text, nullable | Optional description |
| status | Enum | `todo`, `in_progress`, `done` |
| created_at | DateTime(timezone) | Creation timestamp |
| updated_at | DateTime(timezone) | Last update |
| is_deleted | Boolean | Soft delete flag |

**Relationships**: project, tenant

---

### UsageEvent (`app/models/usage_event.py`)

Logs feature usage for metering/analytics.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| tenant_id | UUID (FK → tenants) | Foreign key |
| feature_name | String(100) | e.g. `project_created`, `task_created`, `user_login` |
| usage_count | Integer | Default 1 |
| timestamp | DateTime(timezone) | When the event occurred |

---

## 6. Authentication & Authorization

### JWT Payload

```json
{
  "sub": "<user_id>",
  "tenant_id": "<tenant_id>",
  "role": "owner|admin|member",
  "exp": "<expiration_timestamp>"
}
```

- **sub**: User ID (subject)
- **tenant_id**: Tenant ID (always from server, never from client)
- **role**: User role for RBAC
- **exp**: Expiration (default 30 minutes)

### Auth Flow

1. **Register** (`POST /auth/register`): Creates a new tenant and owner user. Returns JWT.
2. **Login** (`POST /auth/login`): Validates email/password, checks tenant exists and user is active. Logs `user_login` usage event. Returns JWT.
3. **Protected endpoints**: Require `Authorization: Bearer <token>`. `get_current_user` decodes JWT, loads user from DB, verifies `is_active`.

### RBAC Matrix

| Action | Owner | Admin | Member |
|--------|-------|-------|--------|
| Create project | ✓ | ✓ | ✗ |
| Update project | ✓ | ✓ | ✗ |
| Delete project (soft) | ✓ | ✓ | ✗ |
| List/Get project | ✓ | ✓ | ✓ |
| Create task | ✓ | ✓ | ✓ |
| Update task | ✓ | ✓ | ✓ |
| Delete task (soft) | ✓ | ✓ | ✓ |
| List/Get task | ✓ | ✓ | ✓ |

`require_role("owner", "admin")` is used for project create/update/delete.

---

## 7. API Endpoints

### Authentication

| Method | Endpoint | Auth | Body | Response |
|--------|----------|------|------|----------|
| POST | /auth/register | - | `{email, password, tenant_name}` | `{access_token, token_type}` |
| POST | /auth/login | - | `{email, password}` | `{access_token, token_type}` |

### Users & Tenants

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /users/me | Bearer | Current user (no hashed_password) |
| GET | /tenants/me | Bearer | Current tenant |

### Projects

| Method | Endpoint | Auth | Query Params | Description |
|--------|----------|------|--------------|-------------|
| GET | /projects/ | Bearer | `search`, `skip`, `limit`, `sort`, `order` | List projects (paginated) |
| POST | /projects/ | Bearer (owner/admin) | - | Create project |
| GET | /projects/{id} | Bearer | - | Get project |
| PUT | /projects/{id} | Bearer (owner/admin) | - | Update project |
| DELETE | /projects/{id} | Bearer (owner/admin) | - | Soft delete project |
| GET | /projects/{id}/tasks | Bearer | `search`, `status`, `skip`, `limit`, `sort`, `order` | List tasks in project |
| POST | /projects/{id}/tasks | Bearer | - | Create task in project |

### Tasks

| Method | Endpoint | Auth | Query Params | Description |
|--------|----------|------|--------------|-------------|
| GET | /tasks/ | Bearer | `search`, `status`, `skip`, `limit`, `sort`, `order` | List all tenant tasks |
| GET | /tasks/{id} | Bearer | - | Get task |
| PUT | /tasks/{id} | Bearer | - | Update task |
| DELETE | /tasks/{id} | Bearer | - | Soft delete task |

### Pagination Response

```json
{
  "total": 42,
  "skip": 0,
  "limit": 10,
  "items": [...]
}
```

### Health

| Method | Endpoint | Auth | Response |
|--------|----------|------|----------|
| GET | /health | - | `{status: "ok"}` |

---

## 8. Services & Business Logic

### Usage Service (`app/services/usage.py`)

- **log_usage_event**: Inserts a row into `usage_events` (e.g. `project_created`, `task_created`, `user_login`).
- **count_tenant_projects**: Counts non-deleted projects for a tenant (used for subscription limits).
- **count_project_tasks**: Counts non-deleted tasks in a project.

### Subscription Service (`app/services/subscription.py`)

- **check_project_limit**: Raises `ValueError` if tenant's project count ≥ plan limit. Called before project creation.
- **check_task_limit**: Raises `ValueError` if project's task count ≥ plan limit. Called before task creation.

### Subscription Plans (`app/core/subscription.py`)

| Plan | Project Limit | Tasks per Project |
|------|---------------|-------------------|
| free | 3 | 10 |
| pro | unlimited | unlimited |
| enterprise | unlimited | unlimited |

---

## 9. Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | `postgresql+asyncpg://user:pass@host/db` |
| SECRET_KEY | Yes | - | JWT signing secret |
| ALGORITHM | No | HS256 | JWT algorithm |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | 30 | JWT expiration in minutes |

### Pydantic Settings (`app/core/config.py`)

- Loads from `.env`
- Validates required fields
- `settings` singleton used across the app

---

## 10. Database & Migrations

### Connection

- **Engine**: `create_async_engine` with `asyncpg`
- **Session**: `async_sessionmaker` with `expire_on_commit=False`
- **get_db**: Async generator that yields a session, commits on success, rolls back on error, closes on exit

### Alembic

- **async**: Uses `async_engine_from_config`, `run_async_migrations`
- **metadata**: Imported from `app.db.base`; all models imported in `env.py` so they're registered
- **Commands**:
  - `alembic revision --autogenerate -m "message"` — Generate migration
  - `alembic upgrade head` — Apply migrations

---

## 11. Logging & Observability

### Logging Middleware (`app/core/logging_middleware.py`)

Logs each request with:

- HTTP method
- Path
- user_id (from JWT, or `-` if unauthenticated)
- tenant_id (from JWT, or `-`)
- Response status code
- Duration (ms)

### Usage Events

Stored in `usage_events` table for metering and analytics. Events: `project_created`, `task_created`, `user_login`.

---

## 12. Testing

### Fixtures (`conftest.py`)

- **async_engine**: SQLite in-memory (or `TEST_DATABASE_URL`)
- **db_session**: Async session for tests
- **client**: httpx AsyncClient with overridden `get_db`
- **auth_token**: JWT from registration
- **auth_headers**: `Authorization: Bearer <token>`

### Running Tests

```bash
# SQLite (default)
pytest -v

# PostgreSQL
TEST_DATABASE_URL=postgresql+asyncpg://... pytest -v
```

### Test Coverage

- **test_auth.py**: Register, login, JWT, /users/me
- **test_projects.py**: Create, list, pagination, soft delete
- **test_tasks.py**: Create, list, soft delete
- **test_health.py**: /health endpoint

---

## 13. Deployment

### Docker Compose

- **postgres**: PostgreSQL 15, exposed on 5432, volume for persistence
- **backend**: Build from Dockerfile, depends on postgres, ports 8000

### Dockerfile

- Base: `python:3.11-slim`
- Installs gcc, libpq-dev for asyncpg
- Copies requirements, installs deps, copies app
- CMD: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Run Commands

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

---

## 14. Security Considerations

1. **Tenant ID**: Never accepted from client. Always from JWT / `current_user.tenant_id`.
2. **Password storage**: bcrypt via passlib. Hashed password never in response schemas.
3. **JWT**: HS256, signed with SECRET_KEY. Validate signature on every protected request.
4. **CORS**: Currently allows all origins; restrict in production.
5. **SECRET_KEY**: Must be strong and unique in production; use env vars.
6. **Soft deletes**: All list/get queries filter `is_deleted=False` to hide deleted records.

---

## Appendix: Quick Reference

### Common Query Patterns

```python
# Tenant-scoped project list
select(Project).where(
    Project.tenant_id == current_tenant.id,
    Project.is_deleted.is_(False)
)

# Soft delete
project.is_deleted = True
await db.flush()
```

### Dependency Injection Order

`get_current_user` → `get_current_tenant` → `require_role` (uses `get_current_user`)
