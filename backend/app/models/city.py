from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class City(Base):
    """Local geocoding table: user locations resolve against this, not an external API."""

    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("name", "state"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    latitude: Mapped[float]
    longitude: Mapped[float]
