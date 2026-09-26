import math

import pytest

from app.services.ranking.engine import (
    ProviderMetrics,
    SortOption,
    rank,
    score_provider,
)
from app.services.ranking.weights import Priority, get_weights

# The worked example in docs/ranking.md and docs/architecture.md.
DOCUMENTED = ProviderMetrics(
    provider_id=1,
    quality_score=88,
    years_experience=15,
    cost_index=0.9,
    volume_percentile=0.7,
    distance_miles=6.0,
)


def _ids(ranked: list[tuple[ProviderMetrics, object]]) -> list[int]:
    return [metrics.provider_id for metrics, _ in ranked]


def test_documented_example() -> None:
    breakdown = score_provider(DOCUMENTED, get_weights(Priority.QUALITY), radius_miles=20)

    assert breakdown.overall == pytest.approx(81.548, abs=1e-3)
    assert [c.name for c in breakdown.components] == [
        "quality",
        "experience",
        "cost",
        "volume",
        "distance",
    ]
    assert [c.contribution for c in breakdown.components] == pytest.approx(
        [48.4, 16.148, 3.0, 7.0, 7.0], abs=1e-3
    )
    assert [c.weight for c in breakdown.components] == pytest.approx([0.55, 0.2, 0.05, 0.1, 0.1])
    assert breakdown.overall == pytest.approx(sum(c.contribution for c in breakdown.components))


def test_without_location_distance_is_dropped_and_weights_renormalized() -> None:
    metrics = ProviderMetrics(
        provider_id=1, quality_score=88, years_experience=15, cost_index=0.9, volume_percentile=0.7
    )

    breakdown = score_provider(metrics, get_weights(Priority.QUALITY), radius_miles=None)

    assert breakdown.component("distance") is None
    assert [c.name for c in breakdown.components] == ["quality", "experience", "cost", "volume"]
    assert math.fsum(c.weight for c in breakdown.components) == pytest.approx(1.0)
    # 0.55 of the remaining 0.90.
    quality = breakdown.component("quality")
    assert quality is not None
    assert quality.weight == pytest.approx(0.55 / 0.9)
    assert breakdown.overall == pytest.approx(sum(c.contribution for c in breakdown.components))


def test_distance_without_radius_is_an_error() -> None:
    with pytest.raises(ValueError, match="radius"):
        score_provider(DOCUMENTED, get_weights(Priority.BALANCED), radius_miles=None)


# Chosen so every sort column gives a different order.
SORT_CANDIDATES = [
    ProviderMetrics(
        1,
        quality_score=90,
        years_experience=5,
        cost_index=1.3,
        volume_percentile=0.5,
        distance_miles=12.0,
    ),
    ProviderMetrics(
        2,
        quality_score=70,
        years_experience=25,
        cost_index=0.7,
        volume_percentile=0.5,
        distance_miles=3.0,
    ),
    ProviderMetrics(
        3,
        quality_score=80,
        years_experience=15,
        cost_index=1.0,
        volume_percentile=0.5,
        distance_miles=None,
    ),
]


@pytest.mark.parametrize(
    ("sort", "expected_ids"),
    [
        (SortOption.QUALITY, [1, 3, 2]),
        (SortOption.EXPERIENCE, [2, 3, 1]),
        (SortOption.COST, [2, 3, 1]),
        # No distance sorts last.
        (SortOption.DISTANCE, [2, 1, 3]),
    ],
)
def test_sort_by_column(sort: SortOption, expected_ids: list[int]) -> None:
    ranked = rank(SORT_CANDIDATES, Priority.BALANCED, radius_miles=20, sort=sort)

    assert _ids(ranked) == expected_ids


def test_sort_by_match_orders_by_overall_descending() -> None:
    ranked = rank(SORT_CANDIDATES, Priority.BALANCED, radius_miles=20, sort="match")

    overalls = [breakdown.overall for _, breakdown in ranked]
    assert overalls == sorted(overalls, reverse=True)
    assert len(set(overalls)) == len(overalls)


def test_order_does_not_depend_on_input_order() -> None:
    for sort in SortOption:
        forward = rank(SORT_CANDIDATES, Priority.BALANCED, 20, sort)
        backward = rank(list(reversed(SORT_CANDIDATES)), Priority.BALANCED, 20, sort)
        assert _ids(forward) == _ids(backward)


@pytest.mark.parametrize("sort", list(SortOption))
def test_ties_break_by_quality_then_id(sort: SortOption) -> None:
    # Quality normalization clamps at 100, so 100 and 105 score identically: an exact tie
    # on every sort column and on overall, leaving only quality_score and id to decide.
    base = dict(years_experience=10, cost_index=1.0, volume_percentile=0.5, distance_miles=5.0)
    candidates = [
        ProviderMetrics(provider_id=3, quality_score=100, **base),
        ProviderMetrics(provider_id=2, quality_score=100, **base),
        ProviderMetrics(provider_id=9, quality_score=105, **base),
    ]

    ranked = rank(candidates, Priority.BALANCED, radius_miles=20, sort=sort)

    assert len({breakdown.overall for _, breakdown in ranked}) == 1
    assert _ids(ranked) == [9, 2, 3]


def test_priority_changes_the_order() -> None:
    excellent_but_expensive = ProviderMetrics(
        provider_id=1, quality_score=95, years_experience=20, cost_index=1.45, volume_percentile=0.6
    )
    cheap_but_average = ProviderMetrics(
        provider_id=2, quality_score=70, years_experience=20, cost_index=0.6, volume_percentile=0.6
    )
    candidates = [excellent_but_expensive, cheap_but_average]

    assert _ids(rank(candidates, Priority.QUALITY, radius_miles=None)) == [1, 2]
    assert _ids(rank(candidates, Priority.COST, radius_miles=None)) == [2, 1]


def test_rank_rejects_unknown_sort_or_priority() -> None:
    with pytest.raises(ValueError):
        rank(SORT_CANDIDATES, Priority.BALANCED, radius_miles=20, sort="alphabetical")
    with pytest.raises(ValueError):
        rank(SORT_CANDIDATES, "cheapest", radius_miles=20)
