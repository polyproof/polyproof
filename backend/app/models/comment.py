from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            "(conjecture_id IS NOT NULL AND project_id IS NULL) OR "
            "(conjecture_id IS NULL AND project_id IS NOT NULL)",
            name="comments_target_check",
        ),
        Index(
            "idx_comments_conjecture_created",
            "conjecture_id",
            "created_at",
            postgresql_where=text("conjecture_id IS NOT NULL"),
        ),
        Index(
            "idx_comments_project_created",
            "project_id",
            "created_at",
            postgresql_where=text("project_id IS NOT NULL"),
        ),
        Index(
            "idx_comments_conjecture_summary",
            "conjecture_id",
            text("created_at DESC"),
            postgresql_where=text("conjecture_id IS NOT NULL AND is_summary = TRUE"),
        ),
        Index(
            "idx_comments_project_summary",
            "project_id",
            text("created_at DESC"),
            postgresql_where=text("project_id IS NOT NULL AND is_summary = TRUE"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conjecture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conjectures.id", ondelete="CASCADE"),
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"),
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_summary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
