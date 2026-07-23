"""Tests for task state machine."""
import pytest
from httpx import AsyncClient

from app.models.task import Task


@pytest.mark.asyncio
async def test_list_available_tasks(
    client: AsyncClient,
    auth_headers: dict,
    test_task: Task,
):
    """GET /tasks/available returns pending tasks."""
    resp = await client.get("/api/v1/tasks/available", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == str(test_task.id)


@pytest.mark.asyncio
async def test_list_available_tasks_filtered_by_level(
    client: AsyncClient,
    auth_headers: dict,
    test_task: Task,          # level=1
    db_session,               # need a level=2 task
):
    """Filtering by level only returns matching tasks."""
    import uuid
    t2 = Task(
        id=uuid.uuid4(),
        level=2,
        title="Level 2 task",
        status="pending",
        base_contribution=100,
    )
    db_session.add(t2)
    await db_session.commit()

    resp = await client.get("/api/v1/tasks/available?level=1", headers=auth_headers)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["tasks"]]
    assert str(test_task.id) in ids
    assert str(t2.id) not in ids


@pytest.mark.asyncio
async def test_claim_task_success(
    client: AsyncClient,
    auth_headers: dict,
    test_task: Task,
    test_node,
):
    """Node can claim a pending task."""
    resp = await client.post("/api/v1/tasks/claim", headers=auth_headers, json={
        "node_id": str(test_node.id),
        "preferred_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"]["id"] == str(test_task.id)
    assert data["task"]["status"] == "claimed"


@pytest.mark.asyncio
async def test_claim_task_not_owned_node(
    client: AsyncClient,
    auth_headers: dict,
    test_task: Task,
    db_session,
):
    """Cannot claim with a node you don't own."""
    import uuid
    from app.models.node import Node
    other_node = Node(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),   # different user
        node_name="other",
        hardware_info={},
        status="online",
    )
    db_session.add(other_node)
    await db_session.commit()

    resp = await client.post("/api/v1/tasks/claim", headers=auth_headers, json={
        "node_id": str(other_node.id),
        "preferred_level": 1,
    })
    # node_not_found or node_not_owned depending on lookup order
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_task_details(
    client: AsyncClient,
    auth_headers: dict,
    test_task: Task,
):
    """GET /tasks/{id} returns task details."""
    resp = await client.get(f"/api/v1/tasks/{test_task.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(test_task.id)
    assert data["title"] == test_task.title


@pytest.mark.asyncio
async def test_get_task_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET /tasks/{nonexistent} returns 404."""
    resp = await client.get(
        f"/api/v1/tasks/{'00000000-0000-0000-0000-000000000000'}",
        headers=auth_headers,
    )
    assert resp.status_code == 404
