"""
firefly-scheduler · Router · Admin
管理接口：创建任务 / 查看统计 / 手动干预
（v0.1 简化版，无权限控制，后续加 admin 角色校验）
"""
import uuid
import json
import io
import asyncio
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.task import Task
from app.models.node import Node
from app.models.user import User
from app.models.contribution import ContributionLog
from app.utils.minio_client import minio_client
from app.config import settings
from app.routers.node import get_current_user

bearer = HTTPBearer()

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/tasks")
async def create_task(
    name: str = Form("simulated-task"),
    level: int = Form(1),
    base_contribution: int = Form(10),
    timeout_sec: int = Form(3600),
    max_retries: int = Form(3),
    config: str = Form("{}"),
    package: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    手动创建任务（v0.1 用模拟任务验证流程）
    可选上传任务包 zip，服务端存到 MinIO，claim 时返回预签名下载 URL
    """
    task_id = str(uuid.uuid4())
    task_package_url = None

    if package is not None:
        data = await package.read()
        object_name = f"tasks/{task_id}/package.zip"
        await asyncio.to_thread(
            minio_client.put_object,
            settings.minio_bucket,
            object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type="application/zip",
        )
        task_package_url = object_name

    try:
        config_json = json.loads(config) if isinstance(config, str) else config
    except json.JSONDecodeError:
        config_json = {}

    task = Task(
        id=task_id,
        name=name,
        level=level,
        status="pending",
        base_contribution=base_contribution,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
        task_package_url=task_package_url,
        config_json=json.dumps(config_json),
    )
    db.add(task)
    await db.flush()

    return {
        "task_id": task.id,
        "status": "pending",
        "task_package_url": task_package_url,
        "message": "Task created successfully",
    }


# ─────────────────────────────────────
# GET /stats  全局统计概览
# ─────────────────────────────────────
@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """返回系统全局统计"""
    # 节点统计
    node_count = await db.execute(select(func.count(Node.id)))
    online_nodes = await db.execute(
        select(func.count(Node.id)).where(Node.status == "online")
    )
    busy_nodes = await db.execute(
        select(func.count(Node.id)).where(Node.status == "busy")
    )

    # 任务统计
    task_pending = await db.execute(
        select(func.count(Task.id)).where(Task.status == "pending")
    )
    task_running = await db.execute(
        select(func.count(Task.id)).where(Task.status.in_(["claimed", "running"]))
    )
    task_completed = await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )
    task_failed = await db.execute(
        select(func.count(Task.id)).where(Task.status == "failed")
    )

    # 用户统计
    user_count = await db.execute(select(func.count(User.id)))

    return {
        "nodes": {
            "total": node_count.scalar_one(),
            "online": online_nodes.scalar_one(),
            "busy": busy_nodes.scalar_one(),
        },
        "tasks": {
            "pending": task_pending.scalar_one(),
            "running": task_running.scalar_one(),
            "completed": task_completed.scalar_one(),
            "failed": task_failed.scalar_one(),
        },
        "users": {
            "total": user_count.scalar_one(),
        },
    }


# ─────────────────────────────────────
# POST /tasks/{task_id}/reset  重置失败任务
# ─────────────────────────────────────
@router.post("/tasks/{task_id}/reset")
async def reset_task(task_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """将 failed 任务重置为 pending，重新进入队列"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "pending"
    task.retry_count = 0
    task.claimed_by = None
    task.claimed_at = None

    await db.flush()
    return {"task_id": task.id, "status": "pending", "message": "Task reset"}
