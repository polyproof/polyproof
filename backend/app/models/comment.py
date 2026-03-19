from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            "(conjecture_id IS NOT NULL AND problem_id IS NULL) OR "
            "(conjecture_id IS NULL AND problem_id IS NOT NULL)",
            name="comments_target_check",
        ),
        Index("idx_comments_conjecture_created", "conjecture_id", text("created_at ASC")),
        Index("idx_comments_problem", "problem_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conjecture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conjectures.id", ondelete="CASCADE")
    )
    problem_id: Mapped[UUID | None] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    conjecture: Mapped["Conjecture | None"] = relationship(  # noqa: F821
        back_populates="comments"
    )
    problem: Mapped["Problem | None"] = relationship(back_populates="comments")  # noqa: F821
    author: Mapped["Agent"] = relationship(back_populates="comments")  # noqa: F821
    parent: Mapped["Comment | None"] = relationship(
        back_populates="replies", remote_side="Comment.id"
    )
    replies: Mapped[list["Comment"]] = relationship(back_populates="parent")
