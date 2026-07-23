"""节点 API：注册、心跳、状态管理"""
import secrets
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, Node, User, NodeStatus
from app.api.auth import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/nodes", tags=["节点"])
settings = get_settings()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class NodeRegister(BaseModel):
    gpu_model: str | None = None
    gpu_vram_gb: float | None = None
    gpu_count: int = 1
    cpu_cores: int | None = None
    ram_gb: float | None = None
    capabilities: list[str] = []
    max_batch_size: int | None = None
    supports_bf16: bool = False


class NodeInfo(BaseModel):
    id: UUID
    node_key: str
    status: str
    gpu_model: str | None
    gpu_vram_gb: float | None
    gpu_count: int
    capabilities: list[str]
    total_tasks_completed: int
    total_compute_score: float
    last_heartbeat: datetime | None

    class Config:
        from_attributes = True


class HeartbeatOut(BaseModel):
    status: str
    tasks_in_progress: int


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=dict)
async def register_node(
    info: NodeRegister,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为当前用户注册一个新节点，返回 node_key（需安全保存）"""
    node_key = f"fn_{secrets.token_hex(24)}"  # firefly-node key

    node = Node(
        node_key=node_key,
        user_id=current_user.id,
        status=NodeStatus.ONLINE.value,
        gpu_model=info.gpu_model,
        gpu_vram_gb=info.gpu_vram_gb,
        gpu_count=info.gpu_count,
        cpu_cores=info.cpu_cores,
        ram_gb=info.ram_gb,
        capabilities=info.capabilities,
        max_batch_size=info.max_batch_size,
        supports_bf16=info.supports_bf16,
        last_heartbeat=datetime.utcnow(),
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)

    return {
        "node_id": str(node.id),
        "node_key": node_key,
        "message": "请妥善保管 node_key，它是节点的唯一凭证",
    }


@router.get("/my", response_model=list[NodeInfo])
async def list_my_nodes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有节点"""
    result = await db.execute(
        select(Node).where(Node.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/{node_id}/heartbeat", response_model=HeartbeatOut)
async def heartbeat(
    node_id: UUID,
    node_key: str,  # query param: ?node_key=fn_xxx
    db: AsyncSession = Depends(get_db),
):
    """节点心跳，更新在线状态"""
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.node_key == node_key)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在或凭证错误")

    node.status = NodeStatus.ONLINE.value
    node.last_heartbeat = datetime.utcnow()
    await db.commit()

    # TODO: 查询 Redis，获取该节点当前进行中的任务数
    tasks_in_progress = 0

    return HeartbeatOut(status=node.status, tasks_in_progress=tasks_in_progress)


@router.post("/{node_id}/offline")
async def set_offline(
    node_id: UUID,
    node_key: str,
    db: AsyncSession = Depends(get_db),
):
    """节点主动下线"""
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.node_key == node_key)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    node.status = NodeStatus.OFFLINE.value
    await db.commit()
    return {"status": "ok"}
