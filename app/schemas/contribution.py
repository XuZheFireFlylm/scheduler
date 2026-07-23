"""Contribution Pydantic schemas."""
import uuid
from datetime import datetime
from pydantic import BaseModel


class ContributionLogRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None = None
    amount: int
    type: str          # earn | bonus | deduct | penalty
    description: str | None = None
    balance_after: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ContributionsSummary(BaseModel):
    total_contribution: int
    logs: list[ContributionLogRead]
