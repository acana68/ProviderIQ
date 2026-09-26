"""Property-based tests: invariants that must hold for any valid input."""

from dataclasses import replace
from random import Random

from hypothesis import given
from hypothesis import strategies as st

from app.services.ranking.engine import (
    ProviderMetrics,
    SortOption,
    rank,
    score_provider,
)
from app.services.ranking.weights import Priority, get_weights

# Floating-point slack: effective weights can sum to 1 +/- a few ulps.
EPSILON = 1e-9

finite = {"allow_nan": False, "allow_infinity": False}
radii = st.floats(min_value=0.5, max_value=200, **finite)
priorities = st.sampled_from(list(Priority))
sorts = st.sampled_from(list(SortOption))
non_negative_deltas = st.floats(min_value=0, max_value=50, **finite)


@st.composite
def metrics(draw: st.DrawFn, provider_id: int | None = None) -> ProviderMetrics:
    return ProviderMetrics(
        provider_id=draw(st.integers(1, 10**6)) if provider_id is None else provider_id,
        # Ranges extend past the normal bounds, to cover the clamping.
        quality_score=draw(st.floats(min_value=0, max_value=120, **finite)),
        years_experience=draw(st.floats(min_value=0, max_value=70, **finite)),
        cost_index=draw(st.floats(min_value=0, max_value=3, **finite)),
        volume_percentile=draw(st.floats(min_value=0, max_value=1.2, **finite)),
        distance_miles=draw(st.none() | st.floats(min_value=0, max_value=300, **finite)),
    )


@st.composite
def candidate_lists(draw: st.DrawFn) -> list[ProviderMetrics]:
    ids = draw(st.lists(st.integers(1, 10**6), max_size=25, unique=True))
    return [draw(metrics(provider_id=i)) for i in ids]


@given(metrics(), priorities, radii)
def test_overall_is_between_0_and_100(
    m: ProviderMetrics, priority: Priority, radius: float
) -> None:
    overall = score_provider(m, get_weights(priority), radius).overall

    assert -EPSILON <= overall <= 100 + EPSILON


@given(metrics(), priorities, radii)
def test_contributions_sum_to_overall(
    m: ProviderMetrics, priority: Priority, radius: float
) -> None:
    breakdown = score_provider(m, get_weights(priority), radius)

    assert abs(sum(c.contribution for c in breakdown.components) - breakdown.overall) <= EPSILON
    assert abs(sum(c.weight for c in breakdown.components) - 1) <= EPSILON


def _overall(m: ProviderMetrics, priority: Priority, radius: float) -> float:
    return score_provider(m, get_weights(priority), radius).overall


@given(metrics(), priorities, radii, non_negative_deltas)
def test_higher_quality_never_lowers_overall(
    m: ProviderMetrics, priority: Priority, radius: float, delta: float
) -> None:
    better = replace(m, quality_score=m.quality_score + delta)

    assert _overall(better, priority, radius) >= _overall(m, priority, radius)


@given(metrics(), priorities, radii, non_negative_deltas)
def test_more_experience_never_lowers_overall(
    m: ProviderMetrics, priority: Priority, radius: float, delta: float
) -> None:
    better = replace(m, years_experience=m.years_experience + delta)

    assert _overall(better, priority, radius) >= _overall(m, priority, radius)


@given(metrics(), priorities, radii, st.floats(min_value=0, max_value=1, **finite))
def test_higher_volume_never_lowers_overall(
    m: ProviderMetrics, priority: Priority, radius: float, delta: float
) -> None:
    better = replace(m, volume_percentile=m.volume_percentile + delta)

    assert _overall(better, priority, radius) >= _overall(m, priority, radius)


@given(metrics(), priorities, radii, st.floats(min_value=0, max_value=1, **finite))
def test_lower_cost_never_lowers_overall(
    m: ProviderMetrics, priority: Priority, radius: float, fraction: float
) -> None:
    cheaper = replace(m, cost_index=m.cost_index * fraction)

    assert _overall(cheaper, priority, radius) >= _overall(m, priority, radius)


@given(metrics(), priorities, radii, st.floats(min_value=0, max_value=1, **finite))
def test_shorter_distance_never_lowers_overall(
    m: ProviderMetrics, priority: Priority, radius: float, fraction: float
) -> None:
    distance = radius if m.distance_miles is None else m.distance_miles
    m = replace(m, distance_miles=distance)
    closer = replace(m, distance_miles=distance * fraction)

    assert _overall(closer, priority, radius) >= _overall(m, priority, radius)


@given(candidate_lists(), priorities, sorts, radii, st.randoms())
def test_rank_is_sorted_and_independent_of_input_order(
    candidates: list[ProviderMetrics],
    priority: Priority,
    sort: SortOption,
    radius: float,
    random: Random,
) -> None:
    ranked = rank(candidates, priority, radius, sort)
    shuffled = list(candidates)
    random.shuffle(shuffled)

    assert [m.provider_id for m, _ in rank(shuffled, priority, radius, sort)] == [
        m.provider_id for m, _ in ranked
    ]
    assert sorted(m.provider_id for m, _ in ranked) == sorted(m.provider_id for m in candidates)
    for (a, score_a), (b, score_b) in zip(ranked, ranked[1:], strict=False):
        match sort:
            case SortOption.MATCH:
                assert score_a.overall >= score_b.overall
            case SortOption.QUALITY:
                assert a.quality_score >= b.quality_score
            case SortOption.EXPERIENCE:
                assert a.years_experience >= b.years_experience
            case SortOption.COST:
                assert a.cost_index <= b.cost_index
            case SortOption.DISTANCE:
                if a.distance_miles is None:
                    assert b.distance_miles is None
                elif b.distance_miles is not None:
                    assert a.distance_miles <= b.distance_miles
