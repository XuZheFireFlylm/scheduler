"""Contribution service — atomic balance updates and log writing."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.contribution import ContributionLog


async def award_contribution(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    log_type: str,          # "earn" | "bonus"
    description: str,
    node_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> tuple[User, ContributionLog]:
    """
    Atomically award contribution points to a user and write the log.

    Returns (updated_user, log_entry).
    """
    # Lock the user row to prevent concurrent balance corruption
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Atomic update
    user.total_contribution += amount
    balance_after = user.total_contribution

    # Write log
    log = ContributionLog(
        user_id=user_id,
        node_id=node_id,
        task_id=task_id,
        amount=amount,
        type=log_type,
        balance_after=balance_after,
        description=description,
    )
    db.add(log)

    await db.commit()
    await db.refresh(user)
    await db.refresh(log)

    return user, log


async def deduct_contribution(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    log_type: str,          # "deduct" | "penalty"
    description: str,
    node_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> tuple[User, ContributionLog]:
    """
    Atomically deduct contribution points (min 0) and write the log.
    """
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    deducted = min(user.total_contribution, amount)
    user.total_contribution -= deducted
    balance_after = user.total_contribution

    log = ContributionLog(
        user_id=user_id,
        node_id=node_id,
        task_id=task_id,
        amount=-deducted,
        type=log_type,
        balance_after=balance_after,
        description=description,
    )
    db.add(log)

    await db.commit()
    await db.refresh(user)
    await db.refresh(log)

    return user, log


async def get_contribution_logs(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
) -> list[ContributionLog]:
    """Get recent contribution logs for a user."""
    result = await db.execute(
        select(ContributionLog)
        .where(ContributionLog.user_id == user_id)
        .order_by(ContributionLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
