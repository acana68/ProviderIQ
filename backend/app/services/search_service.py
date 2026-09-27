"""Ranked provider search, and scoring a single provider the same way a search would.

Pipeline: resolve the city -> bounding-box prefilter in SQL -> exact haversine distance,
dropping anything outside the radius -> rank -> paginate -> explain -> log.
"""

import logging
import math
import time

from app.core.errors import (
    ConditionsUnavailableError,
    InvalidSearchError,
    LocationNotFoundError,
)
from app.models import City, Provider
from app.repositories.provider_repository import (
    PeerPercentiles,
    ProviderRepository,
    SearchCandidate,
    SearchFilters,
    SpecialtyMedians,
)
from app.repositories.reference_repository import ReferenceRepository
from app.repositories.search_log_repository import SearchLogRepository
from app.schemas.common import Location
from app.schemas.provider import ProviderDetail, ScoredProviderDetail
from app.schemas.score import ProviderScore
from app.schemas.search import (
    DEFAULT_RADIUS_MILES,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.explanation import (
    CMS_WORDING,
    SYNTHETIC_WORDING,
    PeerComparison,
    explain,
    peer_noun,
)
from app.services.geo import bounding_box, haversine_miles
from app.services.imputation import impute
from app.services.ranking.engine import (
    ProviderMetrics,
    SortOption,
    effective_weights,
    rank,
    score_provider,
)
from app.services.ranking.weights import Priority, get_weights

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        providers: ProviderRepository,
        reference: ReferenceRepository,
        search_logs: SearchLogRepository,
    ) -> None:
        self.providers = providers
        self.reference = reference
        self.search_logs = search_logs

    def search(self, request: SearchRequest) -> SearchResponse:
        start = time.perf_counter()
        if request.condition is not None and not self.reference.has_conditions():
            # Checked first: a slug from another dataset shouldn't read as a typo.
            raise ConditionsUnavailableError()
        errors = _distance_without_location_errors(request.priority, request.sort, request.location)
        specialty_id, condition_id, slug_errors = self._resolve_slugs(request)
        if errors or slug_errors:
            # Everything wrong with the criteria at once, not just the first problem.
            raise InvalidSearchError(errors + slug_errors)
        city = self.resolve_city(request.location)
        radius = request.radius_miles if city is not None else None

        candidates = self.providers.search_candidates(
            SearchFilters(
                specialty_id=specialty_id,
                condition_id=condition_id,
                min_quality_score=request.min_quality_score,
                min_years_experience=request.min_years_experience,
                accepting_new_patients=request.accepting_new_patients,
                bounding_box=(
                    None
                    if city is None
                    else bounding_box(city.latitude, city.longitude, request.radius_miles)
                ),
            )
        )
        by_id: dict[int, SearchCandidate] = {}
        metrics: list[ProviderMetrics] = []
        for candidate in candidates:
            distance = _distance(candidate.provider, city)
            # The bounding box is only a prefilter; this is the exact radius check.
            if distance is not None and distance > request.radius_miles:
                continue
            by_id[candidate.provider.id] = candidate
            metrics.append(
                _metrics(candidate.provider, candidate.percentiles, candidate.medians, distance)
            )

        # Scores and order come from ProviderMetrics alone; peer percentiles are only
        # attached afterwards, for the explanations of the page being returned.
        ranked = rank(metrics, request.priority, radius, request.sort)
        offset = (request.page - 1) * request.page_size
        items = []
        for m, breakdown in ranked[offset : offset + request.page_size]:
            candidate = by_id[m.provider_id]
            peers = _peer_comparison(candidate.provider, candidate.percentiles)
            items.append(
                SearchResult.build(candidate.provider, m, breakdown, explain(breakdown, m, peers))
            )
        # Built before logging: a failed log write rolls back the session, and the results
        # must not depend on it.
        response = SearchResponse(
            items=items,
            page=request.page,
            page_size=request.page_size,
            total=len(ranked),
            total_pages=math.ceil(len(ranked) / request.page_size),
            priority=request.priority,
            sort=request.sort,
            weights_used={
                name: round(weight, 3)
                for name, weight in effective_weights(
                    get_weights(request.priority), include_distance=city is not None
                ).items()
            },
        )

        latency_ms = (time.perf_counter() - start) * 1000
        self._record(request, specialty_id, len(ranked), latency_ms)
        return response

    def score_provider_detail(
        self,
        provider: Provider,
        priority: Priority,
        location: Location | None,
        radius_miles: float | None,
    ) -> ScoredProviderDetail:
        """The provider's detail plus the score a search with these settings would give.

        Uses the same percentile query, distance calculation, and engine as search(), so
        the numbers match that provider's search result exactly.
        """
        errors = _distance_without_location_errors(priority, None, location)
        if errors:
            raise InvalidSearchError(errors)
        city = self.resolve_city(location, field="city")
        radius = (radius_miles or DEFAULT_RADIUS_MILES) if city is not None else None
        percentiles = self.providers.get_peer_percentiles(provider.id)
        # The provider was just loaded, so it has percentiles.
        assert percentiles is not None
        medians = self.providers.get_specialty_medians(provider.specialty_id)
        metrics = _metrics(provider, percentiles, medians, _distance(provider, city))
        breakdown = score_provider(metrics, get_weights(priority), radius)
        return ScoredProviderDetail(
            **ProviderDetail.from_model(provider).model_dump(),
            distance_miles=(
                None if metrics.distance_miles is None else round(metrics.distance_miles, 1)
            ),
            score=ProviderScore.from_breakdown(breakdown),
            explanation=explain(breakdown, metrics, _peer_comparison(provider, percentiles)),
        )

    def _resolve_slugs(
        self, request: SearchRequest
    ) -> tuple[int | None, int | None, list[dict[str, str]]]:
        """Slugs -> ids, plus an error entry for each unknown slug."""
        errors = []
        specialty_id = condition_id = None
        if request.specialty is not None:
            specialty = self.reference.get_specialty_by_slug(request.specialty)
            if specialty is None:
                errors.append({"field": "specialty", "message": "Unknown specialty"})
            else:
                specialty_id = specialty.id
        if request.condition is not None:
            condition = self.reference.get_condition_by_slug(request.condition)
            if condition is None:
                errors.append({"field": "condition", "message": "Unknown condition"})
            else:
                condition_id = condition.id
        return specialty_id, condition_id, errors

    def resolve_city(self, location: Location | None, field: str = "location") -> City | None:
        """The matching city (name case-insensitive), or LocationNotFoundError."""
        if location is None:
            return None
        city = self.reference.get_city(location.city, location.state)
        if city is None:
            raise LocationNotFoundError(field)
        return city

    def _record(
        self, request: SearchRequest, specialty_id: int | None, result_count: int, latency_ms: float
    ) -> None:
        """Log line plus search_logs row. Neither includes the condition or the city."""
        state = request.location.state if request.location is not None else None
        logger.info(
            "search",
            extra={
                "source": request.source,
                "parser_used": request.parser_used,
                "specialty": request.specialty,
                "state": state,
                "priority": request.priority.value,
                "sort": request.sort.value,
                "result_count": result_count,
                "latency_ms": round(latency_ms, 2),
            },
        )
        try:
            self.search_logs.add(
                source=request.source,
                parser_used=request.parser_used,
                specialty_id=specialty_id,
                state=state,
                priority=request.priority.value,
                result_count=result_count,
                latency_ms=latency_ms,
            )
        # Any failure: observability must never break the search itself.
        except Exception:
            logger.warning("Could not write search_logs row", exc_info=True)


def _distance_without_location_errors(
    priority: Priority, sort: SortOption | None, location: Location | None
) -> list[dict[str, str]]:
    """Distance only exists relative to a location. Without one, priority=distance would
    quietly become a profile with its main weight dropped, and sort=distance would quietly
    become the match order, so both are rejected instead."""
    if location is not None:
        return []
    errors = []
    if priority == Priority.DISTANCE:
        errors.append({"field": "priority", "message": "priority=distance requires a location"})
    if sort == SortOption.DISTANCE:
        errors.append({"field": "sort", "message": "sort=distance requires a location"})
    return errors


def _distance(provider: Provider, city: City | None) -> float | None:
    if city is None:
        return None
    return haversine_miles(city.latitude, city.longitude, provider.latitude, provider.longitude)


def _metrics(
    provider: Provider,
    percentiles: PeerPercentiles,
    medians: SpecialtyMedians,
    distance: float | None,
) -> ProviderMetrics:
    """The engine's input. Of the peer percentiles, only volume's is part of the score.

    A missing quality or experience is scored as the specialty median and flagged; see
    services/imputation.py for why. The engine itself never sees a missing value.
    """
    quality = impute(provider.quality_score, medians.quality)
    experience = impute(provider.years_experience, medians.experience)
    return ProviderMetrics(
        provider_id=provider.id,
        quality_score=quality.value,
        years_experience=experience.value,
        cost_index=provider.cost_index,
        volume_percentile=percentiles.volume,
        distance_miles=distance,
        quality_imputed=quality.imputed,
        experience_imputed=experience.imputed,
    )


def _peer_comparison(provider: Provider, percentiles: PeerPercentiles) -> PeerComparison:
    """Explanation input. Needs the provider's specialty loaded."""
    return PeerComparison(
        quality=percentiles.quality,
        experience=percentiles.experience,
        cost=percentiles.cost,
        volume=percentiles.volume,
        peers=peer_noun(provider.specialty.slug, provider.specialty.name),
        wording=CMS_WORDING if provider.data_source == "cms" else SYNTHETIC_WORDING,
    )
