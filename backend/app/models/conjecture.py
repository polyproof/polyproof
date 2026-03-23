from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class Conjecture(Base):
    __tablename__ = "conjectures"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'decomposed', 'proved', 'disproved', 'invalid')",
            name="conjectures_status_check",
        ),
        CheckConstraint(
            "priority IN ('critical', 'high', 'normal', 'low')",
            name="conjectures_priority_check",
        ),
        Index("idx_conjectures_parent", "parent_id"),
        Index("idx_conjectures_project_status", "project_id", "status"),
        Index("idx_conjectures_project_priority", "project_id", "priority"),
        Index("idx_conjectures_project_created", "project_id", text("created_at DESC")),
        Index(
            "idx_conjectures_unique_child",
            "parent_id",
            "lean_statement",
            unique=True,
            postgresql_where=text("status != 'invalid'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conjectures.id", ondelete="RESTRICT"),
    )
    lean_statement: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(8), default="normal", nullable=False)
    sorry_proof: Mapped[str | None] = mapped_column(Text)
    proof_lean: Mapped[str | None] = mapped_column(Text)
    proved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    disproved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
