"""Nodes API router — /nodes/*."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.node import (
    NodeRegister, NodeHeartbeat, NodeRead,
    HeartbeatResponse, NodesList,
)
from app.services.node_service import (
    register_node,
    get_node,
    get_user_nodes,
    update_node_heartbeat,
)
from app.services.task_service import extend_task_heartbeat
from app.api.auth import get_current_user

router = APIRouter(prefix="/nodes", tags=["nodes"])


def _require_owned_node(db: AsyncSession, node_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Raise 403 if the node doesn't belong to the current user."""
    pass  # implemented inline per route


@router.post("/register", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
async def register_node_route(
    body: NodeRegister,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new node (device) for the authenticated user."""
    node = await register_node(
        db=db,
        user_id=user_id,
        node_name=body.node_name,
        hardware_info=body.hardware_info,
        max_task_level=body.max_task_level,
    )
    return node


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    body: NodeHeartbeat,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Periodic heartbeat — keeps the node alive and extends running task TTL."""
    node = await get_node(db, body.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node_not_found")
    if node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")

    node = await update_node_heartbeat(db, node)

    # Extend running task TTL if node has one
    from app.models.task import Task
    result = await db.execute(
        select(Task).where(Task.claimed_by == body.node_id).where(Task.status.in_(["claimed", "running"]))
    )
    running_task = result.scalar_one_or_none()

    remaining = None
    if running_task:
        extended, remaining = await extend_task_heartbeat(db, running_task.id, body.node_id)
        if not extended:
            remaining = None

    return HeartbeatResponse(
        status=node.status,
        running_task_id=running_task.id if running_task else None,
        time_until_expiry=remaining,
    )


@router.get("/me", response_model=NodesList)
async def list_my_nodes(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all nodes belonging to the current user."""
    nodes = await get_user_nodes(db, user_id)
    return NodesList(nodes=nodes)


@router.get("/{node_id}", response_model=NodeRead)
async def get_node_route(
    node_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific node's details."""
    node = await get_node(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node_not_found")
    if node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")
    return node
