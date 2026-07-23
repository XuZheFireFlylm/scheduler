"""Submissions API router — /tasks/{task_id}/result, /tasks/{task_id}/fail."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.task import TaskResultRequest, TaskResultResponse
from app.services.task_service import submit_task_result, mark_task_failed, TaskClaimError
from app.services.node_service import get_node
from app.api.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskFailRequest(BaseModel):
    node_id: uuid.UUID
    error_message: str | None = None


@router.post("/{task_id}/result", response_model=TaskResultResponse)
async def submit_result(
    task_id: uuid.UUID,
    body: TaskResultRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit task training result. Awards contribution points."""
    # Verify node ownership
    node = await get_node(db, body.node_id)
    if not node or node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")

    try:
        task, contribution_earned = await submit_task_result(
            db=db,
            task_id=task_id,
            node_id=body.node_id,
            result_package_url=body.result_package_url,
            result_package_hash=body.result_package_hash,
            metrics=body.metrics.model_dump() if body.metrics else None,
        )
    except TaskClaimError as e:
        raise HTTPException(status_code=400, detail=e.code)

    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    return TaskResultResponse(
        task_id=task.id,
        status="completed",
        contribution_earned=contribution_earned,
        balance_after=user.total_contribution if user else 0,
    )


@router.post("/{task_id}/fail")
async def report_failure(
    task_id: uuid.UUID,
    body: TaskFailRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Report that a task failed (e.g. OOM, CUDA error).
    Handles retry logic: re-queues if retries remain, otherwise archives.
    """
    node = await get_node(db, body.node_id)
    if not node or node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")

    try:
        task = await mark_task_failed(db, task_id, error_message=body.error_message)
    except TaskClaimError as e:
        raise HTTPException(status_code=400, detail=e.code)

    return {
        "task_id": task.id,
        "status": task.status,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
    }
