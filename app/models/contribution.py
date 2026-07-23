"""Contribution Log ORM model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ContributionLog(Base):
    __tablename__ = "contribution_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # Amount: positive = earn/bonus, negative = deduct/penalty
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # Type: earn | bonus | deduct | penalty
    type: Mapped[str] = mapped_column(String(16), nullable=False)

    # Balance snapshot after this transaction
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # ── Relations ────────────────────────────────────────────────────────────
    user = relationship("User", back_populates="contribution_logs")

    def __repr__(self) -> str:
        return f"<ContributionLog {self.type} {self.amount} for user {self.user_id}>"
