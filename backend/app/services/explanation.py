"""Plain-English explanations of a score, built from templates (no LLM).

Built only from the score breakdown and the provider's own metrics, so an explanation
can never claim something the score doesn't reflect. This is the one place scores are
rounded for display.
"""

from app.services.ranking.engine import ComponentName, ProviderMetrics, ScoreBreakdown

_LABELS: dict[ComponentName, str] = {
    "quality": "quality",
    "experience": "experience",
    "cost": "cost",
    "volume": "patient volume",
    "distance": "distance",
}


def explain(breakdown: ScoreBreakdown, metrics: ProviderMetrics) -> str:
    """E.g. "Ranked mainly on quality (48.4 of 81.5 points). 15 years of experience,
    6.0 miles away, cost 10% below average."
    """
    # max() keeps the first of equal contributions, i.e. the earlier component.
    top = max(breakdown.components, key=lambda c: c.contribution)
    headline = (
        f"Ranked mainly on {_LABELS[top.name]} "
        f"({top.contribution:.1f} of {breakdown.overall:.1f} points)."
    )

    facts = [_experience_text(metrics.years_experience)]
    if metrics.distance_miles is not None:
        facts.append(f"{metrics.distance_miles:.1f} miles away")
    facts.append(_cost_text(metrics.cost_index))
    return f"{headline} {', '.join(facts)}."


def _experience_text(years: float) -> str:
    rounded = round(years)
    return f"{rounded} year{'' if rounded == 1 else 's'} of experience"


def _cost_text(cost_index: float) -> str:
    """cost_index 0.9 -> "cost 10% below average"; within half a percent -> "average cost"."""
    percent = round((cost_index - 1) * 100)
    if percent == 0:
        return "average cost"
    direction = "above" if percent > 0 else "below"
    return f"cost {abs(percent)}% {direction} average"
