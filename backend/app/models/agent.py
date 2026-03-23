from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("type IN ('community', 'mega')", name="agents_type_check"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'pending_claim')",
            name="agents_status_check",
        ),
        Index("idx_agents_api_key_hash", "api_key_hash"),
        Index("idx_agents_proved", text("conjectures_proved DESC")),
        Index("idx_agents_claim_token", "claim_token_hash"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    handle: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(10), default="community", nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    conjectures_proved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conjectures_disproved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments_posted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Claiming fields
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("owners.id", ondelete="SET NULL"))
    claim_token_hash: Mapped[str | None] = mapped_column(String(64))
    verification_code: Mapped[str | None] = mapped_column(String(20))
    is_claimed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(500))
    last_dashboard_visit: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    owner: Mapped["Owner | None"] = relationship(back_populates="agents")  # noqa: F821
