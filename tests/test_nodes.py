"""Tests for node module."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_node(
    client: AsyncClient,
    auth_headers: dict,
):
    """POST /nodes/register creates a node."""
    resp = await client.post("/api/v1/nodes/register", headers=auth_headers, json={
        "node_name": "My RTX 4090",
        "hardware_info": {
            "cpu": {"model": "AMD Ryzen 9 7950X", "cores": 16, "threads": 32},
            "gpu": {"model": "NVIDIA RTX 4090", "vram_gb": 24, "cuda_version": "12.1"},
            "memory_gb": 64,
            "disk_gb": 2000,
            "os": "Ubuntu 22.04 LTS",
            "client_version": "0.1.0",
        },
        "max_task_level": 3,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["node_name"] == "My RTX 4090"
    assert data["status"] == "offline"
    assert data["max_task_level"] == 3
    assert data["reputation_score"] == 100


@pytest.mark.asyncio
async def test_list_my_nodes(
    client: AsyncClient,
    auth_headers: dict,
    test_node,
):
    """GET /nodes/me lists user's nodes."""
    resp = await client.get("/api/v1/nodes/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) >= 1
    assert any(n["id"] == str(test_node.id) for n in data["nodes"])


@pytest.mark.asyncio
async def test_heartbeat(
    client: AsyncClient,
    auth_headers: dict,
    test_node,
):
    """POST /nodes/heartbeat updates last_heartbeat."""
    resp = await client.post(
        "/api/v1/nodes/heartbeat",
        headers=auth_headers,
        json={"node_id": str(test_node.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("online", "offline", "busy")
    assert data["running_task_id"] is None  # no running task


@pytest.mark.asyncio
async def test_heartbeat_unknown_node(
    client: AsyncClient,
    auth_headers: dict,
):
    """Heartbeat with unknown node_id returns 404."""
    import uuid
    resp = await client.post(
        "/api/v1/nodes/heartbeat",
        headers=auth_headers,
        json={"node_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_node_details(
    client: AsyncClient,
    auth_headers: dict,
    test_node,
):
    """GET /nodes/{id} returns node details."""
    resp = await client.get(f"/api/v1/nodes/{test_node.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["node_name"] == test_node.node_name
