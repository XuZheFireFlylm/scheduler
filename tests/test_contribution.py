"""Tests for contribution service."""
import pytest
from httpx import AsyncClient

from app.models.task import Task
from app.models.node import Node


@pytest.mark.asyncio
async def test_get_my_contributions_empty(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
):
    """New user starts with 0 contribution."""
    resp = await client.get("/api/v1/users/me/contributions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contribution"] == 0
    assert data["logs"] == []


@pytest.mark.asyncio
async def test_task_claim_then_result_flow(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    test_node,
    test_task,
    db_session,
):
    """
    Full happy path: claim → start → result
    Tests the contribution award on task completion.
    """
    # 1. Claim
    claim_resp = await client.post("/api/v1/tasks/claim", headers=auth_headers, json={
        "node_id": str(test_node.id),
        "preferred_level": 1,
    })
    assert claim_resp.status_code == 200

    # 2. Start
    task_id = claim_resp.json()["task"]["id"]
    start_resp = await client.post(
        f"/api/v1/tasks/{task_id}/start",
        headers=auth_headers,
        json={"node_id": str(test_node.id)},
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "running"

    # 3. Submit result (skip heartbeat + training for unit test)
    result_resp = await client.post(
        f"/api/v1/tasks/{task_id}/result",
        headers=auth_headers,
        json={
            "node_id": str(test_node.id),
            "result_package_url": "https://minio.local/results/test.tar.gz",
            "result_package_hash": "sha256:abc123",
            "metrics": {"loss": 0.01, "steps": 500, "training_time_seconds": 3600},
        },
    )
    assert result_resp.status_code == 200
    data = result_resp.json()
    assert data["status"] == "completed"
    assert data["contribution_earned"] == 50  # base_contribution from fixture task

    # 4. Check contributions
    contrib_resp = await client.get("/api/v1/users/me/contributions", headers=auth_headers)
    assert contrib_resp.status_code == 200
    assert contrib_resp.json()["total_contribution"] == 50
    assert len(contrib_resp.json()["logs"]) == 1
    assert contrib_resp.json()["logs"][0]["type"] == "earn"


@pytest.mark.asyncio
async def test_result_with_invalid_hash_rejected(
    client: AsyncClient,
    auth_headers: dict,
    test_node,
    test_task,
):
    """Submitting a result without sha256: prefix is rejected."""
    # Claim first
    claim_resp = await client.post("/api/v1/tasks/claim", headers=auth_headers, json={
        "node_id": str(test_node.id),
        "preferred_level": 1,
    })
    task_id = claim_resp.json()["task"]["id"]

    result_resp = await client.post(
        f"/api/v1/tasks/{task_id}/result",
        headers=auth_headers,
        json={
            "node_id": str(test_node.id),
            "result_package_url": "https://minio.local/results/test.tar.gz",
            "result_package_hash": "abc123wrong",   # missing sha256: prefix
        },
    )
    assert result_resp.status_code == 400
