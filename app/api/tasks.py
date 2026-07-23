"""Tasks API router — /tasks/* (claim / available / heartbeat / start)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.task import (
    TaskClaimRequest, TaskClaimResponse, ClaimedTask,
    TaskStartRequest, TaskStartResponse,
    TaskList, AvailableTask, TaskRead,
)
from app.services.task_service import (
    get_available_tasks,
    get_task,
    claim_task,
    start_task,
    TaskClaimError,
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/available", response_model=TaskList)
async def list_available_tasks(
    level: int | None = Query(default=None, ge=1, le=3),
    limit: int = Query(default=10, ge=1, le=50),
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List tasks currently available for claiming.
    Does NOT claim — just returns the queue for the client to browse.
    """
    tasks = await get_available_tasks(db, level=level, limit=limit)
    return TaskList(tasks=[
        AvailableTask(
            id=t.id,
            level=t.level,
            title=t.title,
            description=t.description,
            base_contribution=t.base_contribution,
        )
        for t in tasks
    ])


@router.post("/claim", response_model=TaskClaimResponse)
async def claim_task_route(
    body: TaskClaimRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Atomically claim one task.
    - Uses Redis SETNX distributed lock to prevent double-claim
    - Assigns the highest-level pending task the node is eligible for
    - Returns task package URL + deadline
    """
    try:
        task = await claim_task(db, body.node_id, preferred_level=body.preferred_level)
    except TaskClaimError as e:
        status_map = {
            "node_not_found": 404,
            "node_banned": 403,
            "reputation_too_low": 403,
            "no_available_tasks": 404,
        }
        raise HTTPException(
            status_code=status_map.get(e.code, 400),
            detail=e.code,
        )

    # Verify node belongs to this user
    from app.services.node_service import get_node
    node = await get_node(db, body.node_id)
    if not node or node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")

    from app.core.config import get_settings
    from datetime import timedelta
    settings = get_settings()

    claimed_at = task.claimed_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    deadline = claimed_at + timedelta(seconds=settings.TASK_RUN_TTL_SECONDS)

    return TaskClaimResponse(task=ClaimedTask(
        id=task.id,
        status=task.status,
        level=task.level,
        title=task.title,
        task_package_url=task.task_package_url,
        task_package_hash=task.task_package_hash,
        claimed_at=task.claimed_at,
        deadline=deadline,
    ))


@router.post("/{task_id}/start", response_model=TaskStartResponse)
async def start_task_route(
    task_id: uuid.UUID,
    body: TaskStartRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a claimed task as running. Client calls this after starting training."""
    from app.services.node_service import get_node
    node = await get_node(db, body.node_id)
    if not node or node.user_id != user_id:
        raise HTTPException(status_code=403, detail="node_not_owned")

    try:
        task = await start_task(db, task_id, body.node_id)
    except TaskClaimError as e:
        raise HTTPException(status_code=400, detail=e.code)

    from app.core.config import get_settings
    from datetime import timedelta
    settings = get_settings()
    deadline = task.started_at + timedelta(seconds=settings.TASK_RUN_TTL_SECONDS)

    return TaskStartResponse(
        task_id=task.id,
        status=task.status,
        started_at=task.started_at,
        deadline=deadline,
    )


@router.get("/{task_id}", response_model=TaskRead)
async def get_task_route(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get task details."""
    task = await get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task
