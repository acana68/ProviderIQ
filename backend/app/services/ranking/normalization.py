"""Map each raw provider metric onto [0, 1], where higher is always better.

Every function uses fixed bounds, never the min/max of the current result set, so a
provider's score doesn't depend on who else matched the search.

Inputs outside the meaningful range but still valid (a quality of 105, a cost index of
2.0, a distance beyond the radius) are clamped. Inputs that can only come from a bug
(NaN, infinity, negatives, a non-positive radius) raise ValueError instead of being
silently scored.
"""

import math

# ln(31): experience reaches 1.0 at 30 years.
_EXPERIENCE_LOG_CAP = math.log(1 + 30)


def normalize_quality(score: float) -> float:
    """quality_score / 100, clamped to [0, 1].

    Linear, because quality_score is already a rating on a fixed 0-100 scale: a 10-point
    difference means the same thing anywhere on it, so no reshaping is needed.
    """
    _check_non_negative("quality score", score)
    return _clamp01(score / 100)


def normalize_experience(years: float) -> float:
    """min(1, ln(1 + years) / ln(31)): 0 years -> 0, 5 -> 0.52, 10 -> 0.70, 30+ -> 1.

    Logarithmic, for diminishing returns: going from 2 to 10 years in practice matters far
    more than going from 20 to 28. The +1 keeps 0 years at exactly 0 (ln 1 = 0), and the cap
    at 30 years stops very long careers from outscoring everything else.
    """
    _check_non_negative("years of experience", years)
    return min(1.0, math.log1p(years) / _EXPERIENCE_LOG_CAP)


def normalize_cost(cost_index: float) -> float:
    """clamp(1.5 - cost_index, 0, 1): 0.5 -> 1, 1.0 (average) -> 0.5, 1.5 -> 0.

    Linear over the index range where real providers sit (roughly 0.5-1.5), centered so
    an average-cost provider lands exactly in the middle. Linear, because each 10% of cost
    is worth the same to a patient whether it's the cheapest or the dearest provider.
    Beyond the range it clamps rather than rewarding extreme outliers further.
    """
    _check_non_negative("cost index", cost_index)
    return _clamp01(1.5 - cost_index)


def normalize_volume(percentile: float) -> float:
    """The provider's patient-volume percentile within their specialty, clamped to [0, 1].

    A percentile, not the raw count, because volumes differ by specialty (primary care
    sees thousands of patients a year, oncology hundreds), so raw counts can't be
    compared. The percentile is computed over the whole specialty elsewhere, so here it's
    already on the right scale.
    """
    _check_non_negative("volume percentile", percentile)
    return _clamp01(percentile)


def normalize_distance(distance_miles: float, radius_miles: float) -> float:
    """clamp(1 - distance / radius, 0, 1): at the center -> 1, at the radius edge -> 0.

    Linear falloff relative to the user's own radius, so "close" means close for this
    search: 5 miles is far in a 6-mile search but near in a 50-mile one. Results are
    filtered to the radius, so the clamp only matters for rounding at the edge.
    """
    _check_non_negative("distance", distance_miles)
    _check_finite("radius", radius_miles)
    if radius_miles <= 0:
        raise ValueError(f"radius must be positive, got {radius_miles}")
    return _clamp01(1 - distance_miles / radius_miles)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _check_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value}")


def _check_non_negative(name: str, value: float) -> None:
    _check_finite(name, value)
    if value < 0:
        raise ValueError(f"{name} must not be negative, got {value}")
