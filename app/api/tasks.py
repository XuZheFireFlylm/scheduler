"""任务 API：创建任务、领取、状态查询"""
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, Task, Node, TaskSubmission, TaskStatus, NodeStatus
from app.api.auth import get_current_user
from app.api.nodes import NodeInfo
from app.core.config import get_settings

router = APIRouter(prefix="/tasks", tags=["任务"])
settings = get_settings()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    task_type: str
    version: str
    config: dict
    train_data_s3_prefix: str
    base_model: str
    priority: int = 5
    expires_at: datetime | None = None


class TaskOut(BaseModel):
    id: UUID
    task_type: str
    version: str
    status: str
    config: dict
    base_model: str
    assigned_count: int
    completed_count: int
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskClaim(BaseModel):
    node_id: UUID
    node_key: str


class TaskPackage(BaseModel):
    """节点领取任务后拿到的完整训练包"""
    submission_id: UUID
    task_id: UUID
    base_model: str
    config: dict
    train_data_s3_prefix: str
    submission_id_key: str  # 用于回调的身份标识


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

async def check_offline_nodes(db: AsyncSession):
    """后台任务：标记超时离线的节点"""
    from datetime import timedelta
    threshold = datetime.utcnow() - timedelta(seconds=settings.NODE_OFFLINE_THRESHOLD_SECONDS)
    await db.execute(
        update(Node)
        .where(Node.last_heartbeat < threshold, Node.status != NodeStatus.OFFLINE.value)
        .values(status=NodeStatus.OFFLINE.value)
    )
    await db.commit()


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新训练任务（管理员操作，v0.1 阶段由核心开发者操作）"""
    task = Task(
        task_type=task_data.task_type,
        version=task_data.version,
        config=task_data.config,
        train_data_s3_prefix=task_data.train_data_s3_prefix,
        base_model=task_data.base_model,
        priority=task_data.priority,
        expires_at=task_data.expires_at,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/", response_model=list[TaskOut])
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    version: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出训练任务（公开）"""
    query = select(Task).order_by(Task.priority, Task.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if version:
        query = query.where(Task.version == version)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/claim", response_model=TaskPackage)
async def claim_task(
    claim: TaskClaim,
    db: AsyncSession = Depends(get_db),
):
    """节点领取一个训练任务（无用户态认证，用 node_key 验证）"""
    # 验证节点
    result = await db.execute(
        select(Node).where(Node.id == claim.node_id, Node.node_key == claim.node_key)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在或凭证错误")
    if node.status == NodeStatus.OFFLINE.value:
        raise HTTPException(status_code=400, detail="节点已离线，请先重新上线")

    # 查找可领取的 PENDING 任务（按优先级 + 时间排序）
    result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.PENDING.value)
        .order_by(Task.priority, Task.created_at)
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="暂无可用任务，稍后再试")

    # 创建提交记录
    submission = TaskSubmission(
        task_id=task.id,
        node_id=node.id,
        status=TaskStatus.ASSIGNED.value,
        started_at=datetime.utcnow(),
    )
    db.add(submission)

    # 更新任务状态（ASSIGNED 计数+1）
    task.assigned_count += 1
    await db.commit()
    await db.refresh(submission)

    return TaskPackage(
        submission_id=submission.id,
        task_id=task.id,
        base_model=task.base_model,
        config=task.config,
        train_data_s3_prefix=task.train_data_s3_prefix,
        submission_id_key=str(submission.id),
    )


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: UUID,
    node_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """节点查询自己提交记录的状态"""
    result = await db.execute(
        select(TaskSubmission, Node, Task)
        .join(Node, TaskSubmission.node_id == Node.id)
        .join(Task, TaskSubmission.task_id == Task.id)
        .where(TaskSubmission.id == submission_id, Node.node_key == node_key)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="提交记录不存在")

    submission, node, task = row
    return {
        "id": submission.id,
        "task_id": submission.task_id,
        "task_type": task.task_type,
        "status": submission.status,
        "compute_score": submission.compute_score,
    }
