from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        CheckConstraint("value IN (1, -1)", name="votes_value_check"),
        CheckConstraint(
            "target_type IN ('problem', 'conjecture', 'comment')",
            name="votes_target_type_check",
        ),
        UniqueConstraint("agent_id", "target_id", "target_type", name="votes_unique"),
        Index("idx_votes_target_agent", "target_id", "target_type", "agent_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
