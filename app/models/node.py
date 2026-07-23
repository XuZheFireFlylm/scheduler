"""Node ORM model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Node(Base):
    __tablename__ = "nodes"

    # UUID primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Display
    node_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Hardware snapshot (JSON — cpu/gpu/memory info)
    hardware_info: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Status: online | offline | busy | banned
    status: Mapped[str] = mapped_column(String(16), default="offline", index=True)

    # Reputation 0–1000
    reputation_score: Mapped[int] = mapped_column(Integer, default=100)

    # Max task level this node can execute (1–3)
    max_task_level: Mapped[int] = mapped_column(Integer, default=1)

    # Last heartbeat timestamp
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Relations ────────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="nodes")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="claimed_by_node")

    def __repr__(self) -> str:
        return f"<Node {self.node_name} [{self.status}]>"
