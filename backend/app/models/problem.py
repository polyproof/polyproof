from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (Index("idx_problems_created", text("created_at DESC")),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lean_header: Mapped[str | None] = mapped_column(Text)
    root_conjecture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conjectures.id", deferrable=True, initially="DEFERRED"),
    )
    last_mega_invocation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
