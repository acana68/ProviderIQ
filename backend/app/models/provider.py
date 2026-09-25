from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.condition import Condition
from app.models.specialty import Specialty

# Plain association table (no extra columns), so it doesn't need a mapped class.
# The composite PK starts with provider_id; the separate condition_id index serves
# "which providers treat X".
provider_conditions = Table(
    "provider_conditions",
    Base.metadata,
    Column("provider_id", ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "condition_id",
        ForeignKey("conditions.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint("credential IN ('MD', 'DO')", name="credential_valid"),
        CheckConstraint("quality_score BETWEEN 0 AND 100", name="quality_score_range"),
        CheckConstraint("complication_rate BETWEEN 0 AND 1", name="complication_rate_range"),
        CheckConstraint("readmission_rate BETWEEN 0 AND 1", name="readmission_rate_range"),
        CheckConstraint("years_experience BETWEEN 0 AND 70", name="years_experience_range"),
        CheckConstraint("cost_index > 0", name="cost_index_positive"),
        CheckConstraint("patient_volume >= 0", name="patient_volume_non_negative"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        # Leading specialty_id also covers the FK and specialty-only filters.
        Index("ix_providers_specialty_id_state", "specialty_id", "state"),
        # Radius search prefilters on a lat/lon bounding box.
        Index("ix_providers_latitude_longitude", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    credential: Mapped[str] = mapped_column(String(2))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    subspecialty: Mapped[str | None] = mapped_column(String(100))

    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(5))
    latitude: Mapped[float]
    longitude: Mapped[float]

    years_experience: Mapped[int]
    quality_score: Mapped[float]
    # 1.0 = regional average; lower is cheaper.
    cost_index: Mapped[float]
    # Annual patients.
    patient_volume: Mapped[int]
    complication_rate: Mapped[float]
    readmission_rate: Mapped[float]
    accepting_new_patients: Mapped[bool] = mapped_column(default=True, server_default=true())

    specialty: Mapped[Specialty] = relationship()
    # passive_deletes: let ON DELETE CASCADE clean up provider_conditions rows.
    conditions: Mapped[list[Condition]] = relationship(
        secondary=provider_conditions, passive_deletes=True
    )
