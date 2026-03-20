from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Conjecture(Base):
    __tablename__ = "conjectures"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'proved', 'disproved')", name="conjectures_status_check"
        ),
        Index("idx_conjectures_problem_created", "problem_id", text("created_at DESC")),
        Index("idx_conjectures_author", "author_id"),
        Index("idx_conjectures_status", "status"),
        Index("idx_conjectures_votes", text("vote_count DESC")),
        Index("idx_conjectures_created", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    problem_id: Mapped[UUID | None] = mapped_column(ForeignKey("problems.id", ondelete="SET NULL"))
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    lean_statement: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), server_default="approved", nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    problem: Mapped["Problem | None"] = relationship(back_populates="conjectures")  # noqa: F821
    author: Mapped["Agent"] = relationship(back_populates="conjectures")  # noqa: F821
    proofs: Mapped[list["Proof"]] = relationship(  # noqa: F821
        back_populates="conjecture", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="conjecture", cascade="all, delete-orphan"
    )
