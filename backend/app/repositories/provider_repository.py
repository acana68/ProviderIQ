from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Provider


@dataclass(frozen=True)
class ProviderFilters:
    specialty_id: int | None = None
    # Two-letter code, uppercase.
    state: str | None = None
    # Matched case-insensitively.
    city: str | None = None
    accepting_new_patients: bool | None = None


class ProviderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_page(
        self, filters: ProviderFilters, *, offset: int, limit: int
    ) -> tuple[Sequence[Provider], int]:
        """One page of providers (specialty loaded) plus the total match count.

        Ordered by last name, first name, then id, so pages never overlap or skip rows.
        """
        conditions = _filter_conditions(filters)
        total = self.session.scalar(select(func.count(Provider.id)).where(*conditions)) or 0
        if offset >= total:
            # Also avoids sending the database an OFFSET beyond its integer range.
            return [], total

        stmt = (
            select(Provider)
            # Many-to-one, so a join adds no duplicate rows.
            .options(joinedload(Provider.specialty))
            .where(*conditions)
            .order_by(Provider.last_name, Provider.first_name, Provider.id)
            .offset(offset)
            .limit(limit)
        )
        return self.session.scalars(stmt).all(), total

    def get(self, provider_id: int) -> Provider | None:
        """A provider with specialty and conditions loaded, or None."""
        stmt = (
            select(Provider)
            .options(joinedload(Provider.specialty), selectinload(Provider.conditions))
            .where(Provider.id == provider_id)
        )
        return self.session.scalars(stmt).one_or_none()


def _filter_conditions(filters: ProviderFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.specialty_id is not None:
        conditions.append(Provider.specialty_id == filters.specialty_id)
    if filters.state is not None:
        conditions.append(Provider.state == filters.state)
    if filters.city is not None:
        conditions.append(func.lower(Provider.city) == filters.city.lower())
    if filters.accepting_new_patients is not None:
        conditions.append(Provider.accepting_new_patients == filters.accepting_new_patients)
    return conditions
