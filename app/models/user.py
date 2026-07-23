"""User ORM model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # Contribution is stored as integer (cents-like unit; 1 unit = 1 contribution point)
    total_contribution: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # ── Relations ────────────────────────────────────────────────────────────
    nodes: Mapped[list["Node"]] = relationship("Node", back_populates="user", lazy="selectin")
    contribution_logs: Mapped[list["ContributionLog"]] = relationship(
        "ContributionLog", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
