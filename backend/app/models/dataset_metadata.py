from datetime import date, datetime

from sqlalchemy import CheckConstraint, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DatasetMetadata(Base):
    """Which dataset the database holds, written by the seed script. Exactly one row.

    GET /dataset reads this rather than the DATA_SOURCE setting, so the API always
    describes the data actually loaded (and shows the CMS disclaimer whenever real data
    is), even when the app runs with a different .env than the seed did.
    """

    __tablename__ = "dataset_metadata"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("source IN ('synthetic', 'cms_nj')", name="source_valid"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    source: Mapped[str] = mapped_column(String(20))
    # When the source data was retrieved; NULL for generated data.
    as_of: Mapped[date | None]
    # Source releases, e.g. "MIPS PY 2024; Medicare utilization CY 2024".
    vintage: Mapped[str | None] = mapped_column(Text)
    seeded_at: Mapped[datetime] = mapped_column(server_default=func.now())
