"""Task Pydantic schemas."""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# ── Task metrics (submitted on result) ────────────────────────────────────────
class TaskMetrics(BaseModel):
    loss: float | None = None
    steps: int | None = None
    training_time_seconds: int | None = None


# ── Available task (GET /tasks/available — no sensitive info) ─────────────────
class AvailableTask(BaseModel):
    id: uuid.UUID
    level: int
    title: str
    description: str | None = None
    base_contribution: int
    task_package_size_mb: int | None = None   # TODO: populate from metadata
    estimated_time_minutes: int | None = None  # TODO: populate from metadata

    model_config = {"from_attributes": True}


class TaskList(BaseModel):
    tasks: list[AvailableTask]


# ── Claim request / response ──────────────────────────────────────────────────
class TaskClaimRequest(BaseModel):
    node_id: uuid.UUID
    preferred_level: int | None = Field(default=1, ge=1, le=3)


class ClaimedTask(BaseModel):
    id: uuid.UUID
    status: str
    level: int
    title: str
    task_package_url: str | None = None
    task_package_hash: str | None = None
    claimed_at: datetime | None = None
    deadline: datetime | None = None

    model_config = {"from_attributes": True}


class TaskClaimResponse(BaseModel):
    task: ClaimedTask


# ── Start request / response ──────────────────────────────────────────────────
class TaskStartRequest(BaseModel):
    node_id: uuid.UUID


class TaskStartResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    started_at: datetime
    deadline: datetime | None = None


# ── Result request / response ─────────────────────────────────────────────────
class TaskResultRequest(BaseModel):
    node_id: uuid.UUID
    result_package_url: str
    result_package_hash: str       # "sha256:..."
    metrics: TaskMetrics | None = None


class TaskResultResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    contribution_earned: int
    balance_after: int


# ── Full task read ─────────────────────────────────────────────────────────────
class TaskRead(BaseModel):
    id: uuid.UUID
    level: int
    title: str
    description: str | None = None
    status: str
    retry_count: int
    max_retries: int
    base_contribution: int
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
