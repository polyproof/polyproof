from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="agents_status_check"),
        CheckConstraint("length(name) <= 100", name="agents_name_length_check"),
        CheckConstraint("length(description) <= 5000", name="agents_description_length_check"),
        Index("idx_agents_api_key_hash", "api_key_hash"),
        Index("idx_agents_reputation", text("reputation DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reputation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conjecture_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proof_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    problems: Mapped[list["Problem"]] = relationship(back_populates="author")  # noqa: F821
    conjectures: Mapped[list["Conjecture"]] = relationship(  # noqa: F821
        back_populates="author"
    )
    proofs: Mapped[list["Proof"]] = relationship(back_populates="author")  # noqa: F821
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")  # noqa: F821
