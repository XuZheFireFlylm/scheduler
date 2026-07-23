"""Node service — registration, heartbeat, status management."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.node import Node
from app.schemas.node import HardwareInfo


async def register_node(
    db: AsyncSession,
    user_id: uuid.UUID,
    node_name: str,
    hardware_info: HardwareInfo,
    max_task_level: int = 1,
) -> Node:
    """Create a new node for a user."""
    node = Node(
        user_id=user_id,
        node_name=node_name,
        hardware_info=hardware_info.model_dump(mode="json"),
        max_task_level=max_task_level,
        status="offline",
        reputation_score=100,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def get_node(db: AsyncSession, node_id: uuid.UUID) -> Node | None:
    result = await db.execute(
        select(Node).where(Node.id == node_id).options(selectinload(Node.user))
    )
    return result.scalar_one_or_none()


async def get_user_nodes(db: AsyncSession, user_id: uuid.UUID) -> list[Node]:
    result = await db.execute(
        select(Node)
        .where(Node.user_id == user_id)
        .order_by(Node.created_at.desc())
    )
    return list(result.scalars().all())


async def update_node_heartbeat(
    db: AsyncSession,
    node: Node,
) -> Node:
    """Update last_heartbeat and ensure status is online."""
    node.last_heartbeat = datetime.now(timezone.utc)
    if node.status == "offline":
        node.status = "online"
    await db.commit()
    await db.refresh(node)
    return node


async def set_node_status(
    db: AsyncSession,
    node: Node,
    status: str,          # online | offline | busy | banned
) -> Node:
    """Set node status explicitly."""
    node.status = status
    if status in ("offline", "banned"):
        node.last_heartbeat = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(node)
    return node


async def penalize_node(
    db: AsyncSession,
    node: Node,
    points: int = 10,
) -> Node:
    """Deduct reputation points. Caps at 0."""
    node.reputation_score = max(0, node.reputation_score - points)
    await db.commit()
    await db.refresh(node)
    return node
