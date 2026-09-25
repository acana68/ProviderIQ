from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SearchLog(Base):
    """One row per search, for observability.

    Deliberately has no free-text query and no condition column: people type their own
    health details into search boxes, so neither is ever stored.
    """

    __tablename__ = "search_logs"
    __table_args__ = (CheckConstraint("source IN ('nl', 'manual')", name="source_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    source: Mapped[str] = mapped_column(String(10))
    parser_used: Mapped[str | None] = mapped_column(String(20))
    specialty_id: Mapped[int | None] = mapped_column(
        ForeignKey("specialties.id", ondelete="SET NULL")
    )
    state: Mapped[str | None] = mapped_column(String(2))
    priority: Mapped[str] = mapped_column(String(20))
    result_count: Mapped[int]
    latency_ms: Mapped[float]
