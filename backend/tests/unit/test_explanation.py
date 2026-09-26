from dataclasses import replace

import pytest

from app.services.explanation import explain
from app.services.ranking.engine import ProviderMetrics, score_provider
from app.services.ranking.weights import Priority, get_weights

DOCUMENTED = ProviderMetrics(
    provider_id=1,
    quality_score=88,
    years_experience=15,
    cost_index=0.9,
    volume_percentile=0.7,
    distance_miles=6.0,
)


def _explain(
    metrics: ProviderMetrics,
    priority: Priority = Priority.QUALITY,
    radius_miles: float | None = 20,
) -> str:
    return explain(score_provider(metrics, get_weights(priority), radius_miles), metrics)


def test_documented_example() -> None:
    assert _explain(DOCUMENTED) == (
        "Ranked mainly on quality (48.4 of 81.5 points). "
        "15 years of experience, 6.0 miles away, cost 10% below average."
    )


def test_names_the_top_contributing_component() -> None:
    nearby = replace(DOCUMENTED, quality_score=60, distance_miles=0.5)

    assert _explain(nearby, Priority.DISTANCE).startswith("Ranked mainly on distance (")


def test_without_location_omits_distance() -> None:
    text = _explain(replace(DOCUMENTED, distance_miles=None), radius_miles=None)

    assert "miles" not in text
    assert text.endswith("15 years of experience, cost 10% below average.")


@pytest.mark.parametrize(
    ("cost_index", "wording"),
    [
        (0.9, "cost 10% below average"),
        (0.55, "cost 45% below average"),
        (1.25, "cost 25% above average"),
        (1.0, "average cost"),
        # Rounds to 0%, so "0% above average" would be silly.
        (1.004, "average cost"),
        (0.996, "average cost"),
    ],
)
def test_cost_wording(cost_index: float, wording: str) -> None:
    assert _explain(replace(DOCUMENTED, cost_index=cost_index)).endswith(f"{wording}.")


def test_singular_year() -> None:
    assert "1 year of experience" in _explain(replace(DOCUMENTED, years_experience=1))
