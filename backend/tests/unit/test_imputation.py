"""Missing quality or experience: scored as the specialty median, flagged, and never an
advantage over a real value."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.services.imputation import FALLBACK, ImputedValue, impute
from app.services.ranking.engine import ProviderMetrics, SortOption, rank, score_provider
from app.services.ranking.weights import Priority, get_weights

finite = {"allow_nan": False, "allow_infinity": False}
priorities = st.sampled_from(list(Priority))
sorts = st.sampled_from(list(SortOption))

BASE = ProviderMetrics(
    provider_id=1,
    quality_score=80,
    years_experience=12,
    cost_index=1.0,
    volume_percentile=0.5,
    distance_miles=5.0,
)


def test_a_reported_value_is_kept() -> None:
    assert impute(72.5, 90.0) == ImputedValue(72.5, imputed=False)
    # Zero is a real value, not a missing one.
    assert impute(0.0, 90.0) == ImputedValue(0.0, imputed=False)


def test_a_missing_value_becomes_the_median() -> None:
    assert impute(None, 88.0) == ImputedValue(88.0, imputed=True)


def test_without_any_median_the_fallback_never_rewards_missing_data() -> None:
    assert impute(None, None) == ImputedValue(FALLBACK, imputed=True)
    assert FALLBACK == 0.0


@given(
    median=st.floats(min_value=0, max_value=99, **finite),
    above_by=st.floats(min_value=0.01, max_value=100, **finite),
    missing_id=st.integers(1, 1000),
    reported_id=st.integers(1001, 2000),
    swap_ids=st.booleans(),
    priority=priorities,
    sort=sorts,
    radius=st.floats(min_value=5, max_value=100, **finite),
)
def test_missing_quality_never_outranks_an_equal_provider_scored_above_the_median(
    median: float,
    above_by: float,
    missing_id: int,
    reported_id: int,
    swap_ids: bool,
    priority: Priority,
    sort: SortOption,
    radius: float,
) -> None:
    """Whatever the priority and sort, and whichever id is lower (ids break ties)."""
    if swap_ids:
        missing_id, reported_id = reported_id, missing_id
    stand_in = impute(None, median)
    missing = replace(
        BASE,
        provider_id=missing_id,
        quality_score=stand_in.value,
        quality_imputed=stand_in.imputed,
    )
    reported = replace(BASE, provider_id=reported_id, quality_score=min(100.0, median + above_by))

    ranked = rank([missing, reported], priority, radius, sort)

    assert [m.provider_id for m, _ in ranked] == [reported_id, missing_id]


@given(
    median=st.floats(min_value=0, max_value=29, **finite),
    above_by=st.floats(min_value=0.01, max_value=40, **finite),
    swap_ids=st.booleans(),
    priority=priorities,
    sort=sorts,
)
def test_missing_experience_never_outranks_an_equal_provider_above_the_median(
    median: float, above_by: float, swap_ids: bool, priority: Priority, sort: SortOption
) -> None:
    missing_id, reported_id = (2, 1) if swap_ids else (1, 2)
    stand_in = impute(None, median)
    missing = replace(
        BASE,
        provider_id=missing_id,
        years_experience=stand_in.value,
        experience_imputed=True,
    )
    # Normalized experience saturates at 30 years, so stay below it to keep a difference.
    reported = replace(BASE, provider_id=reported_id, years_experience=min(30.0, median + above_by))

    ranked = rank([missing, reported], priority, 20, sort)

    assert [m.provider_id for m, _ in ranked] == [reported_id, missing_id]


def test_an_imputed_value_scores_exactly_like_the_same_real_value() -> None:
    """The flag marks the value; it never changes the score."""
    imputed = replace(BASE, quality_imputed=True, experience_imputed=True)
    weights = get_weights(Priority.BALANCED)

    assert score_provider(imputed, weights, 20).overall == score_provider(BASE, weights, 20).overall


def test_the_breakdown_marks_imputed_components() -> None:
    breakdown = score_provider(
        replace(BASE, quality_imputed=True), get_weights(Priority.BALANCED), 20
    )

    assert {c.name: c.imputed for c in breakdown.components} == {
        "quality": True,
        "experience": False,
        "cost": False,
        "volume": False,
        "distance": False,
    }


@pytest.mark.parametrize(
    ("sort", "field", "flag"),
    [
        (SortOption.QUALITY, "quality_score", "quality_imputed"),
        (SortOption.EXPERIENCE, "years_experience", "experience_imputed"),
    ],
)
def test_sorting_by_a_metric_lists_imputed_values_last(
    sort: SortOption, field: str, flag: str
) -> None:
    # The imputed stand-in (a high median) would come first if sorted as a real value.
    imputed_high = replace(BASE, provider_id=1, **{field: 25, flag: True})
    real_mid = replace(BASE, provider_id=2, **{field: 15})
    real_low = replace(BASE, provider_id=3, **{field: 5})

    ranked = rank([imputed_high, real_low, real_mid], Priority.BALANCED, 20, sort)

    assert [m.provider_id for m, _ in ranked] == [2, 3, 1]
