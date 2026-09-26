"""Deterministic provider scoring and ranking. Pure Python: no database, no web framework.

overall        = sum of contributions
contribution_i = 100 * effective_weight_i * normalized_i
effective_weight_i = weight_i / (sum of the weights of the components in use)

Without a location the distance component is dropped, and dividing by the remaining
weights' sum renormalizes them to 1 automatically. Values keep full float precision;
rounding is left to whatever displays them.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.services.ranking.normalization import (
    normalize_cost,
    normalize_distance,
    normalize_experience,
    normalize_quality,
    normalize_volume,
)
from app.services.ranking.weights import Priority, WeightProfile, get_weights

ComponentName = Literal["quality", "experience", "cost", "volume", "distance"]


class SortOption(StrEnum):
    MATCH = "match"
    QUALITY = "quality"
    EXPERIENCE = "experience"
    DISTANCE = "distance"
    COST = "cost"


@dataclass(frozen=True)
class ProviderMetrics:
    provider_id: int
    quality_score: float
    years_experience: float
    cost_index: float
    # Patient-volume percentile within the provider's specialty, in [0, 1].
    volume_percentile: float
    # None when the search has no location.
    distance_miles: float | None = None


@dataclass(frozen=True)
class ComponentScore:
    name: ComponentName
    raw: float
    normalized: float
    # The weight actually applied, after renormalization.
    weight: float
    contribution: float


@dataclass(frozen=True)
class ScoreBreakdown:
    overall: float
    # Always in the order quality, experience, cost, volume, distance; distance is absent
    # when the search has no location.
    components: tuple[ComponentScore, ...]

    def component(self, name: ComponentName) -> ComponentScore | None:
        return next((c for c in self.components if c.name == name), None)


Ranked = tuple[ProviderMetrics, ScoreBreakdown]


def effective_weights(
    weights: WeightProfile, *, include_distance: bool
) -> dict[ComponentName, float]:
    """The weights actually applied, in component order, renormalized to sum to 1.

    Without a location the distance weight is dropped and the rest are divided by their
    sum. (With a location the sum is already 1, so the division changes nothing.)
    """
    configured: dict[ComponentName, float] = {
        "quality": weights.quality,
        "experience": weights.experience,
        "cost": weights.cost,
        "volume": weights.volume,
    }
    if include_distance:
        configured["distance"] = weights.distance
    # Never zero: the quality weight is always at least MIN_QUALITY_WEIGHT.
    total = sum(configured.values())
    return {name: weight / total for name, weight in configured.items()}


def score_provider(
    metrics: ProviderMetrics, weights: WeightProfile, radius_miles: float | None
) -> ScoreBreakdown:
    """Score one provider. radius_miles is required when metrics.distance_miles is set."""
    # name -> (raw value, normalized value), in component order.
    values: dict[ComponentName, tuple[float, float]] = {
        "quality": (metrics.quality_score, normalize_quality(metrics.quality_score)),
        "experience": (metrics.years_experience, normalize_experience(metrics.years_experience)),
        "cost": (metrics.cost_index, normalize_cost(metrics.cost_index)),
        "volume": (metrics.volume_percentile, normalize_volume(metrics.volume_percentile)),
    }
    if metrics.distance_miles is not None:
        if radius_miles is None:
            raise ValueError("radius_miles is required when distance_miles is set")
        values["distance"] = (
            metrics.distance_miles,
            normalize_distance(metrics.distance_miles, radius_miles),
        )

    applied = effective_weights(weights, include_distance="distance" in values)
    components = tuple(
        ComponentScore(
            name=name,
            raw=raw,
            normalized=normalized,
            weight=applied[name],
            contribution=100 * applied[name] * normalized,
        )
        for name, (raw, normalized) in values.items()
    )
    return ScoreBreakdown(overall=sum(c.contribution for c in components), components=components)


def rank(
    candidates: Iterable[ProviderMetrics],
    priority: Priority | str,
    radius_miles: float | None,
    sort: SortOption | str = SortOption.MATCH,
) -> list[Ranked]:
    """Score every candidate and order them.

    `priority` decides how scores are computed; `sort` only picks the ordering column.
    Every sort falls back to the same tie-breaks (overall desc, quality desc, id asc), so
    the order is fully determined by the input values, never by input order.
    """
    weights = get_weights(priority)
    scored = [(m, score_provider(m, weights, radius_miles)) for m in candidates]
    return sorted(scored, key=_SORT_KEYS[SortOption(sort)])


def _tie_break(item: Ranked) -> tuple[float, float, int]:
    metrics, breakdown = item
    return (-breakdown.overall, -metrics.quality_score, metrics.provider_id)


def _by_distance(item: Ranked) -> tuple[object, ...]:
    distance = item[0].distance_miles
    # False sorts before True, so providers without a distance go last.
    return (distance is None, distance or 0.0, *_tie_break(item))


_SORT_KEYS: dict[SortOption, Callable[[Ranked], tuple[object, ...]]] = {
    SortOption.MATCH: _tie_break,
    SortOption.QUALITY: lambda item: (-item[0].quality_score, *_tie_break(item)),
    SortOption.EXPERIENCE: lambda item: (-item[0].years_experience, *_tie_break(item)),
    SortOption.DISTANCE: _by_distance,
    SortOption.COST: lambda item: (item[0].cost_index, *_tie_break(item)),
}
