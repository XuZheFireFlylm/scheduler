"""Task ORM model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Task metadata
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, or 3
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status machine: pending | claimed | running | completed | failed | archived
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # Which node has this task
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # Retry bookkeeping
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Incentive
    base_contribution: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # MinIO references
    task_package_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_package_hash: Mapped[str | None] = mapped_column(String(72), nullable=True)   # "sha256:..."
    result_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String(72), nullable=True)

    # Error message (set when status becomes 'failed')
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relations ────────────────────────────────────────────────────────────
    claimed_by_node: Mapped["Node"] = relationship("Node", back_populates="tasks")

    # DB-level constraints
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 3", name="task_level_range"),
        CheckConstraint("retry_count >= 0", name="task_retry_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Task {self.id} [{self.status}] lvl={self.level}>"
