"""Users API router — /users/*."""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.contribution import ContributionsSummary, ContributionLogRead
from app.services.contribution_service import get_contribution_logs
from app.api.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/contributions", response_model=ContributionsSummary)
async def get_my_contributions(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's total contribution and recent transaction log."""
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    logs = await get_contribution_logs(db, user_id, limit=50)

    return ContributionsSummary(
        total_contribution=user.total_contribution if user else 0,
        logs=[ContributionLogRead.model_validate(log) for log in logs],
    )
