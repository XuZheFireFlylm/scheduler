"""提交结果 API：节点训练完成后回调调度中心"""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, Task, TaskSubmission, Node, TaskStatus, NodeStatus
from app.core.config import get_settings

router = APIRouter(prefix="/submissions", tags=["提交结果"])
settings = get_settings()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SubmissionResult(BaseModel):
    submission_id: UUID
    status: str  # "completed" | "failed"
    final_loss: float | None = None
    steps_completed: int | None = None
    epoch_completed: float | None = None
    lora_weights_s3_path: str | None = None
    log_summary: str | None = None
    error_message: str | None = None


class SubmissionAck(BaseModel):
    success: bool
    compute_score: float
    message: str


# ─── 贡献分计算 ──────────────────────────────────────────────────────────────

def compute_score(
    gpu_vram_gb: float,
    steps_completed: int,
    batch_size: int,
    epochs_completed: float,
) -> float:
    """
    简化版贡献分计算：
    基准分 = GPU显存系数 × (steps × batch_size × epochs)
    GPU系数: RTX3060(12GB)=1.0, RTX4090(24GB)=2.5, A100(40GB)=4.5
    """
    if gpu_vram_gb >= 80:
        gpu_coef = 9.0
    elif gpu_vram_gb >= 40:
        gpu_coef = 4.5
    elif gpu_vram_gb >= 24:
        gpu_coef = 2.5
    elif gpu_vram_gb >= 16:
        gpu_coef = 1.5
    else:
        gpu_coef = 1.0

    base_score = gpu_coef * steps_completed * batch_size * max(epochs_completed, 1)
    return round(base_score, 2)


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/report", response_model=SubmissionAck)
async def report_result(
    result: SubmissionResult,
    node_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    节点训练完成后调用此 API 报告结果。
    这是调度中心的核心写入接口。
    """
    # 验证节点
    result_node = await db.execute(
        select(TaskSubmission, Node)
        .join(Node, TaskSubmission.node_id == Node.id)
        .where(TaskSubmission.id == result.submission_id, Node.node_key == node_key)
    )
    row = result_node.first()
    if not row:
        raise HTTPException(status_code=404, detail="提交记录不存在或凭证错误")

    submission, node = row

    if result.status == "completed":
        submission.status = TaskStatus.COMPLETED.value
        submission.final_loss = result.final_loss
        submission.steps_completed = result.steps_completed
        submission.epoch_completed = result.epoch_completed
        submission.lora_weights_s3_path = result.lora_weights_s3_path
        submission.log_summary = result.log_summary
        submission.completed_at = datetime.utcnow()

        # 计算贡献分
        batch_size = submission.task.config.get("per_device_train_batch_size", 1) if submission.task else 1
        submission.compute_score = compute_score(
            gpu_vram_gb=node.gpu_vram_gb or 12,
            steps_completed=result.steps_completed or 0,
            batch_size=batch_size,
            epochs_completed=result.epoch_completed or 1.0,
        )

        # 更新节点统计
        node.total_tasks_completed += 1
        node.total_compute_score += submission.compute_score

        # 更新任务完成数
        if submission.task:
            submission.task.completed_count += 1
            # 如果某版本任务全部完成，更新状态
            if submission.task.assigned_count > 0 and \
               submission.task.completed_count >= submission.task.assigned_count:
                submission.task.status = TaskStatus.COMPLETED.value

    else:
        submission.status = TaskStatus.FAILED.value
        submission.error_message = result.error_message
        submission.completed_at = datetime.utcnow()

    # 节点状态恢复
    node.status = NodeStatus.ONLINE.value
    await db.commit()

    return SubmissionAck(
        success=result.status == "completed",
        compute_score=submission.compute_score,
        message=f"结果已记录，贡献分 +{submission.compute_score:.1f}",
    )


@router.get("/leaderboard")
async def leaderboard(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """节点贡献排行榜（公开）"""
    result = await db.execute(
        select(Node)
        .order_by(Node.total_compute_score.desc())
        .limit(limit)
    )
    nodes = result.scalars().all()
    return [
        {
            "rank": i + 1,
            "gpu_model": n.gpu_model,
            "total_tasks_completed": n.total_tasks_completed,
            "total_compute_score": n.total_compute_score,
        }
        for i, n in enumerate(nodes)
    ]
