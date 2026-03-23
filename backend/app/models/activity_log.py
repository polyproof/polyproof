from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class ActivityLog(Base):
    __tablename__ = "activity_log"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'comment', 'proof', 'disproof', "
            "'assembly_success', 'assembly_failure', "
            "'decomposition_created', 'decomposition_updated', 'decomposition_reverted', "
            "'priority_changed'"
            ")",
            name="activity_log_event_type_check",
        ),
        Index("idx_activity_project_created", "project_id", text("created_at DESC")),
        Index("idx_activity_project_type", "project_id", "event_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    conjecture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conjectures.id", ondelete="SET NULL"),
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
