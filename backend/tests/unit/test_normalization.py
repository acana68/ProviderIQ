import math
from collections.abc import Callable

import pytest

from app.services.ranking.normalization import (
    normalize_cost,
    normalize_cost_percentile,
    normalize_distance,
    normalize_experience,
    normalize_quality,
    normalize_volume,
)


@pytest.mark.parametrize(
    ("score", "expected"), [(0, 0.0), (50, 0.5), (88, 0.88), (100, 1.0), (150, 1.0)]
)
def test_quality(score: float, expected: float) -> None:
    assert normalize_quality(score) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("years", "expected"),
    [(0, 0.0), (5, 0.5218), (10, 0.6983), (20, 0.8866), (30, 1.0), (45, 1.0)],
)
def test_experience(years: float, expected: float) -> None:
    assert normalize_experience(years) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(
    ("cost_index", "expected"),
    [(0.0, 1.0), (0.5, 1.0), (0.9, 0.6), (1.0, 0.5), (1.5, 0.0), (2.0, 0.0)],
)
def test_cost(cost_index: float, expected: float) -> None:
    assert normalize_cost(cost_index) == pytest.approx(expected)


@pytest.mark.parametrize(("percentile", "expected"), [(0, 0.0), (0.7, 0.7), (1, 1.0), (1.2, 1.0)])
def test_cost_percentile(percentile: float, expected: float) -> None:
    assert normalize_cost_percentile(percentile) == pytest.approx(expected)


@pytest.mark.parametrize(("percentile", "expected"), [(0, 0.0), (0.7, 0.7), (1, 1.0), (1.2, 1.0)])
def test_volume(percentile: float, expected: float) -> None:
    assert normalize_volume(percentile) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("distance", "radius", "expected"),
    [(0, 20, 1.0), (6, 20, 0.7), (20, 20, 0.0), (25, 20, 0.0), (0.5, 1, 0.5)],
)
def test_distance(distance: float, radius: float, expected: float) -> None:
    assert normalize_distance(distance, radius) == pytest.approx(expected)


@pytest.mark.parametrize(
    "normalize", [normalize_quality, normalize_experience, normalize_cost, normalize_volume]
)
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.01])
def test_single_argument_functions_reject_invalid_input(
    normalize: Callable[[float], float], bad: float
) -> None:
    with pytest.raises(ValueError):
        normalize(bad)


@pytest.mark.parametrize(
    ("distance", "radius"),
    [
        (math.nan, 10),
        (-1, 10),
        (math.inf, 10),
        (5, 0),
        (5, -10),
        (5, math.nan),
        (5, math.inf),
    ],
)
def test_distance_rejects_invalid_input(distance: float, radius: float) -> None:
    with pytest.raises(ValueError):
        normalize_distance(distance, radius)
