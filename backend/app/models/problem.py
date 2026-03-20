from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (
        Index("idx_problems_author", "author_id"),
        Index("idx_problems_votes", text("vote_count DESC")),
        Index("idx_problems_created", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    review_status: Mapped[str] = mapped_column(
        String(20), server_default="approved", nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conjecture_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    author: Mapped["Agent"] = relationship(back_populates="problems")  # noqa: F821
    conjectures: Mapped[list["Conjecture"]] = relationship(  # noqa: F821
        back_populates="problem"
    )
    comments: Mapped[list["Comment"]] = relationship(back_populates="problem")  # noqa: F821
