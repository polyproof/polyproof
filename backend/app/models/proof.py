from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Proof(Base):
    __tablename__ = "proofs"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending', 'passed', 'rejected', 'timeout')",
            name="proofs_verification_check",
        ),
        Index("idx_proofs_conjecture_created", "conjecture_id", text("created_at ASC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conjecture_id: Mapped[UUID] = mapped_column(
        ForeignKey("conjectures.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    lean_proof: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    verification_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    conjecture: Mapped["Conjecture"] = relationship(back_populates="proofs")  # noqa: F821
    author: Mapped["Agent"] = relationship(back_populates="proofs")  # noqa: F821
