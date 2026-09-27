from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Double,
    Subquery,
    case,
    exists,
    func,
    select,
    true,
    type_coerce,
)
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Provider, provider_conditions


@dataclass(frozen=True)
class ProviderFilters:
    specialty_id: int | None = None
    # Two-letter code, uppercase.
    state: str | None = None
    # Matched case-insensitively.
    city: str | None = None
    accepting_new_patients: bool | None = None


@dataclass(frozen=True)
class SearchFilters:
    specialty_id: int | None = None
    condition_id: int | None = None
    min_quality_score: float | None = None
    min_years_experience: int | None = None
    accepting_new_patients: bool | None = None
    # (min_lat, max_lat, min_lon, max_lon); a coarse prefilter, not the exact radius.
    bounding_box: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class PeerPercentiles:
    """Where a provider ranks among ALL providers in their specialty, each in [0, 1] with
    1 the best: the fraction of the other providers they beat on that measure.

    Only `volume` feeds the score. The rest exist to explain it (see
    services/explanation.py), so ranking never depends on them. A metric the provider
    doesn't have is None: they have no rank, and their peers are ranked only among the
    providers who have it.
    """

    volume: float
    quality: float | None
    experience: float | None
    # Higher = cheaper.
    cost: float


@dataclass(frozen=True)
class SpecialtyMedians:
    """The median of each optional metric over ALL providers in a specialty who have it
    (the whole dataset's median if none do; None only if nobody has it). A missing
    value is scored as this; see services/imputation.py."""

    quality: float | None
    experience: float | None


@dataclass(frozen=True)
class SearchCandidate:
    provider: Provider
    percentiles: PeerPercentiles
    medians: SpecialtyMedians


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

    def search_candidates(self, filters: SearchFilters) -> list[SearchCandidate]:
        """Every provider matching the filters, with specialty loaded and peer percentiles
        and specialty medians attached. Ordered by id; ranking happens in the caller.

        A minimum quality or experience filter only matches providers who have that
        value: an imputed median must not pass a filter the user set on real numbers.
        """
        percentiles = _peer_percentiles()
        medians = _specialty_medians()
        stmt = (
            select(
                Provider,
                *_percentile_columns(percentiles),
                medians.c.quality,
                medians.c.experience,
            )
            .join(percentiles, percentiles.c.provider_id == Provider.id)
            .join(medians, medians.c.specialty_id == Provider.specialty_id)
            .options(joinedload(Provider.specialty))
            .where(*_search_conditions(filters))
            .order_by(Provider.id)
        )
        return [
            SearchCandidate(
                provider=provider,
                percentiles=PeerPercentiles(*values[:-2]),
                medians=SpecialtyMedians(*values[-2:]),
            )
            for provider, *values in self.session.execute(stmt).all()
        ]

    def get_peer_percentiles(self, provider_id: int) -> PeerPercentiles | None:
        """The same percentiles search_candidates() attaches, for one provider."""
        percentiles = _peer_percentiles()
        row = self.session.execute(
            select(*_percentile_columns(percentiles)).where(
                percentiles.c.provider_id == provider_id
            )
        ).one_or_none()
        return None if row is None else PeerPercentiles(*row)

    def get_specialty_medians(self, specialty_id: int) -> SpecialtyMedians:
        """The same medians search_candidates() attaches, for one specialty."""
        medians = _specialty_medians()
        row = self.session.execute(
            select(medians.c.quality, medians.c.experience).where(
                medians.c.specialty_id == specialty_id
            )
        ).one_or_none()
        # Only a specialty with no providers has no row.
        return SpecialtyMedians(None, None) if row is None else SpecialtyMedians(*row)


def _peer_percentiles() -> Subquery:
    """provider_id -> percent_rank within the provider's specialty, per measure.

    Computed in a subquery over ALL providers, so the outer query's filters can't change
    them: a provider's volume score (and explanation) is the same whatever else the
    search asked for. percent_rank is (rank - 1) / (rows - 1): the fraction of the other
    providers in the specialty ranked below this one. Ties share the lower rank, and a
    provider alone in their specialty gets 0.

    A provider missing the measure gets NULL, and is left out of everyone else's rank:
    the partition also splits on "is it NULL". Otherwise Postgres would sort NULLs last,
    ranking every missing value as the best in the specialty.
    """

    def within_specialty(
        column: ColumnElement[Any], label: str, *, descending: bool = False
    ) -> ColumnElement[float | None]:
        rank = func.percent_rank().over(
            partition_by=(Provider.specialty_id, column.is_(None)),
            order_by=column.desc() if descending else column,
        )
        # SQLAlchemy types percent_rank() as Numeric, which would come back as Decimal.
        # Postgres returns double precision, so read it as a plain float.
        return case((column.is_(None), None), else_=type_coerce(rank, Double())).label(label)

    return select(
        Provider.id.label("provider_id"),
        within_specialty(Provider.patient_volume, "volume"),
        within_specialty(Provider.quality_score, "quality"),
        within_specialty(Provider.years_experience, "experience"),
        # Descending: the cheapest provider ranks highest.
        within_specialty(Provider.cost_index, "cost", descending=True),
    ).subquery("peer_percentiles")


def _specialty_medians() -> Subquery:
    """specialty_id -> the median quality_score and years_experience over ALL providers
    in the specialty (percentile_cont skips NULLs), like the percentiles: filters can't
    change them. A specialty where nobody has the measure uses the whole dataset's."""

    def median(column: ColumnElement[Any], label: str) -> ColumnElement[Any]:
        return func.percentile_cont(0.5).within_group(column).label(label)

    overall = select(
        median(Provider.quality_score, "quality"),
        median(Provider.years_experience, "experience"),
    ).subquery("overall_medians")
    per_specialty = (
        select(
            Provider.specialty_id,
            median(Provider.quality_score, "quality"),
            median(Provider.years_experience, "experience"),
        )
        .group_by(Provider.specialty_id)
        .subquery("per_specialty_medians")
    )

    def with_fallback(name: str) -> ColumnElement[float | None]:
        value = func.coalesce(per_specialty.c[name], overall.c[name])
        # Double: percentile_cont returns double precision, but SQLAlchemy doesn't know.
        return type_coerce(value, Double()).label(name)

    return (
        select(per_specialty.c.specialty_id, with_fallback("quality"), with_fallback("experience"))
        .join(overall, true())
        .subquery("specialty_medians")
    )


def _percentile_columns(percentiles: Subquery) -> list[ColumnElement[float]]:
    """In PeerPercentiles field order."""
    return [percentiles.c[field.name] for field in fields(PeerPercentiles)]


def _search_conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.specialty_id is not None:
        conditions.append(Provider.specialty_id == filters.specialty_id)
    if filters.condition_id is not None:
        # EXISTS rather than a join, so a provider can't appear twice.
        conditions.append(
            exists()
            .where(provider_conditions.c.provider_id == Provider.id)
            .where(provider_conditions.c.condition_id == filters.condition_id)
        )
    if filters.min_quality_score is not None:
        conditions.append(Provider.quality_score >= filters.min_quality_score)
    if filters.min_years_experience is not None:
        conditions.append(Provider.years_experience >= filters.min_years_experience)
    if filters.accepting_new_patients is not None:
        conditions.append(Provider.accepting_new_patients == filters.accepting_new_patients)
    if filters.bounding_box is not None:
        min_lat, max_lat, min_lon, max_lon = filters.bounding_box
        conditions.append(Provider.latitude.between(min_lat, max_lat))
        conditions.append(Provider.longitude.between(min_lon, max_lon))
    return conditions


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
