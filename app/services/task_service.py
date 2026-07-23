"""Task service — core state machine, claiming, result submission."""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.task import Task
from app.models.node import Node
from app.models.user import User
from app.services.redis_lock import TaskLock, get_redis
from app.services.contribution_service import award_contribution

settings = get_settings()


# ── Query helpers ────────────────────────────────────────────────────────────
async def get_available_tasks(
    db: AsyncSession,
    level: int | None = None,
    limit: int = 10,
) -> list[Task]:
    """Return pending tasks, optionally filtered by level."""
    query = (
        select(Task)
        .where(Task.status == "pending")
        .order_by(Task.created_at.asc())
        .limit(limit)
    )
    if level is not None:
        query = query.where(Task.level <= level)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.claimed_by_node).selectinload(Node.user))
    )
    return result.scalar_one_or_none()


# ── Claim ────────────────────────────────────────────────────────────────────
async def claim_task(
    db: AsyncSession,
    node_id: uuid.UUID,
    preferred_level: int | None = None,
) -> Task:
    """
    Atomically claim one available task for a node.

    Uses Redis SETNX distributed lock to prevent double-claim.
    Returns the claimed Task.
    Raises TaskClaimError on failure.
    """
    r = await get_redis()

    # Load node and verify eligibility
    node_res = await db.execute(select(Node).where(Node.id == node_id))
    node: Node | None = node_res.scalar_one_or_none()
    if not node:
        raise TaskClaimError("node_not_found")
    if node.status == "banned":
        raise TaskClaimError("node_banned")
    if node.reputation_score < 10:
        raise TaskClaimError("reputation_too_low")

    # Load candidate tasks (node can only claim tasks up to its max_task_level)
    query = (
        select(Task)
        .where(Task.status == "pending")
        .where(Task.level <= node.max_task_level)
        .order_by(Task.level.desc(), Task.created_at.asc())
        .limit(10)
    )
    if preferred_level is not None:
        query = query.where(Task.level == preferred_level)
    res = await db.execute(query)
    candidates: list[Task] = list(res.scalars().all())

    now = datetime.now(timezone.utc)

    # Try each candidate until we win the lock
    for task in candidates:
        lock = TaskLock(r, str(task.id))
        if await lock.acquire(ttl_seconds=settings.TASK_CLAIM_TTL_SECONDS):
            try:
                # Re-check status under lock (another node may have claimed it)
                fresh_res = await db.execute(
                    select(Task).where(Task.id == task.id).with_for_update()
                )
                fresh_task: Task | None = fresh_res.scalar_one_or_none()
                if not fresh_task or fresh_task.status != "pending":
                    await lock.release()
                    continue  # try next candidate

                # Win! Claim it.
                fresh_task.status = "claimed"
                fresh_task.claimed_by = node_id
                fresh_task.claimed_at = now
                node.status = "busy"
                await db.commit()
                await db.refresh(fresh_task)

                # Set running TTL in Redis
                await lock.set_running(ttl_seconds=settings.TASK_RUN_TTL_SECONDS)
                return fresh_task

            except Exception:
                await db.rollback()
                await lock.release()
                raise
        # else: another node grabbed it, try next

    raise TaskClaimError("no_available_tasks")


# ── Start ─────────────────────────────────────────────────────────────────────
async def start_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    node_id: uuid.UUID,
) -> Task:
    """Mark a claimed task as running. Called by client after starting training."""
    task = await get_task(db, task_id)
    if not task:
        raise TaskClaimError("task_not_found")
    if task.status != "claimed":
        raise TaskClaimError(f"invalid_status_for_start: {task.status}")
    if task.claimed_by != node_id:
        raise TaskClaimError("not_your_task")

    now = datetime.now(timezone.utc)
    task.status = "running"
    task.started_at = now

    # Extend Redis running TTL
    r = await get_redis()
    lock = TaskLock(r, str(task_id))
    await lock.set_running(ttl_seconds=settings.TASK_RUN_TTL_SECONDS)

    await db.commit()
    await db.refresh(task)
    return task


# ── Submit result ────────────────────────────────────────────────────────────
async def submit_task_result(
    db: AsyncSession,
    task_id: uuid.UUID,
    node_id: uuid.UUID,
    result_package_url: str,
    result_package_hash: str,
    metrics: dict | None = None,
) -> tuple[Task, int]:
    """
    Process a task completion:
      1. Validate ownership and status
      2. Store result metadata
      3. Mark completed then archived
      4. Award contribution atomically
      5. Update node status
      6. Clear Redis running lock
    """
    task = await get_task(db, task_id)
    if not task:
        raise TaskClaimError("task_not_found")
    if task.status not in ("claimed", "running"):
        raise TaskClaimError(f"invalid_status_for_result: {task.status}")
    if task.claimed_by != node_id:
        raise TaskClaimError("not_your_task")

    # Validate hash format: "sha256:..."
    if not result_package_hash.startswith("sha256:"):
        raise TaskClaimError("invalid_hash_format")

    now = datetime.now(timezone.utc)
    task.status = "completed"
    task.completed_at = now
    task.result_url = result_package_url
    task.result_hash = result_package_hash

    # Load node + user
    node_res = await db.execute(
        select(Node).where(Node.id == node_id).options(selectinload(Node.user))
    )
    node: Node | None = node_res.scalar_one_or_none()
    user: User | None = node.user if node else None

    contribution_earned = 0
    if user:
        try:
            updated_user, _log = await award_contribution(
                db=db,
                user_id=user.id,
                amount=task.base_contribution,
                log_type="earn",
                description=f"完成任务：{task.title}",
                node_id=node_id,
                task_id=task_id,
            )
            contribution_earned = task.base_contribution
        except Exception:
            contribution_earned = 0  # log failure but don't block submission

    # Node back to online
    if node:
        node.status = "online"

    # Archive
    task.status = "archived"

    await db.commit()
    await db.refresh(task)

    # Clear Redis running lock
    r = await get_redis()
    lock = TaskLock(r, str(task_id))
    await lock.clear_running()

    return task, contribution_earned


# ── Heartbeat (extend running TTL) ───────────────────────────────────────────
async def extend_task_heartbeat(
    db: AsyncSession,
    task_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[bool, int | None]:
    """
    Extend a running task's TTL on heartbeat.
    Returns (extended, remaining_seconds).
    """
    r = await get_redis()
    lock = TaskLock(r, str(task_id))
    ttl = await lock.ttl()
    if ttl > 0:
        await lock.extend_running(ttl_seconds=settings.TASK_RUN_TTL_SECONDS)
        new_ttl = await lock.ttl()
        return True, new_ttl
    return False, None


# ── Mark task failed ──────────────────────────────────────────────────────────
async def mark_task_failed(
    db: AsyncSession,
    task_id: uuid.UUID,
    error_message: str | None = None,
) -> Task:
    """Transition a running/claimed task to failed, handle retries."""
    task = await get_task(db, task_id)
    if not task:
        raise TaskClaimError("task_not_found")

    task.error_message = error_message
    task.retry_count += 1

    # Clear Redis running lock
    r = await get_redis()
    lock = TaskLock(r, str(task_id))
    await lock.clear_running()

    # Return node to online
    if task.claimed_by:
        node_res = await db.execute(select(Node).where(Node.id == task.claimed_by))
        node: Node | None = node_res.scalar_one_or_none()
        if node:
            node.status = "online"

    if task.retry_count < task.max_retries:
        # Re-queue with pending status
        task.status = "pending"
        task.claimed_by = None
        task.claimed_at = None
        task.started_at = None
    else:
        # Permanent failure — archive
        task.status = "archived"
        # Penalize node reputation
        if task.claimed_by:
            node_res = await db.execute(select(Node).where(Node.id == task.claimed_by))
            node: Node | None = node_res.scalar_one_or_none()
            if node:
                node.reputation_score = max(0, node.reputation_score - 20)

    await db.commit()
    await db.refresh(task)
    return task


# ── Exception ────────────────────────────────────────────────────────────────
class TaskClaimError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or code
        super().__init__(self.message)
