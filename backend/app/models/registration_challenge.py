from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class RegistrationChallenge(Base):
    __tablename__ = "registration_challenges"
    __table_args__ = (Index("idx_reg_challenges_name", "name", "completed"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    challenge_statement: Mapped[str] = mapped_column(Text, nullable=False)
    attempts_remaining: Mapped[int] = mapped_column(Integer, server_default="5", nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
