"""Tests for tasks CRUD, search, filter, pagination."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_tasks(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test create task and list tasks."""
    proj_resp = await client.post(
        "/projects/",
        headers=auth_headers,
        json={"name": "Task Project", "description": ""},
    )
    assert proj_resp.status_code == 200
    project_id = proj_resp.json()["id"]
    task_resp = await client.post(
        f"/projects/{project_id}/tasks",
        headers=auth_headers,
        json={"title": "My Task", "description": "", "status": "todo"},
    )
    assert task_resp.status_code == 200
    assert task_resp.json()["title"] == "My Task"
    list_resp = await client.get(
        f"/projects/{project_id}/tasks",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_soft_delete_task(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test soft delete task."""
    proj_resp = await client.post(
        "/projects/",
        headers=auth_headers,
        json={"name": "Del Project", "description": ""},
    )
    project_id = proj_resp.json()["id"]
    task_resp = await client.post(
        f"/projects/{project_id}/tasks",
        headers=auth_headers,
        json={"title": "Del Task", "status": "todo"},
    )
    task_id = task_resp.json()["id"]
    del_resp = await client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert del_resp.status_code == 204
    get_resp = await client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert get_resp.status_code == 404
