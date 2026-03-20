from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('conjecture', 'problem')",
            name="reviews_target_type_check",
        ),
        CheckConstraint(
            "verdict IN ('approve', 'request_changes')",
            name="reviews_verdict_check",
        ),
        UniqueConstraint(
            "target_id",
            "target_type",
            "reviewer_id",
            "version",
            name="uq_reviews_target_reviewer_version",
        ),
        Index("idx_reviews_target", "target_id", "target_type", "version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
