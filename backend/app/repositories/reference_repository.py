from collections.abc import Sequence

from sqlalchemy import Row, exists, func, select
from sqlalchemy.orm import Session

from app.models import Condition, Provider, Specialty, provider_conditions


class ReferenceRepository:
    """Specialties and conditions: the fixed vocabularies behind the search dropdowns."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_specialties_with_provider_counts(self) -> Sequence[Row[tuple[int, str, str, int]]]:
        """Rows with id, slug, name, provider_count, ordered by name.

        Outer join, so a specialty with no providers is listed with a count of 0.
        """
        stmt = (
            select(
                Specialty.id,
                Specialty.slug,
                Specialty.name,
                func.count(Provider.id).label("provider_count"),
            )
            .outerjoin(Provider, Provider.specialty_id == Specialty.id)
            .group_by(Specialty.id)
            .order_by(Specialty.name)
        )
        return self.session.execute(stmt).all()

    def get_specialty_by_slug(self, slug: str) -> Specialty | None:
        return self.session.scalars(select(Specialty).where(Specialty.slug == slug)).one_or_none()

    def list_conditions(self, specialty_id: int | None = None) -> Sequence[Condition]:
        """All conditions, or only those treated by at least one provider in the specialty.

        Conditions have no specialty column; the link is derived through the providers
        who treat them.
        """
        stmt = select(Condition).order_by(Condition.name)
        if specialty_id is not None:
            # EXISTS rather than a join, so each condition appears once.
            stmt = stmt.where(
                exists()
                .where(provider_conditions.c.condition_id == Condition.id)
                .where(provider_conditions.c.provider_id == Provider.id)
                .where(Provider.specialty_id == specialty_id)
            )
        return self.session.scalars(stmt).all()
