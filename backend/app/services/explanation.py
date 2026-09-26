"""Plain-English explanations of a score, built from templates (no LLM).

Built only from the score breakdown, the provider's own metrics, and where they rank
among their specialty peers, so an explanation can never claim something the data
doesn't support. This is the one place numbers are rounded for display.
"""

import math
from dataclasses import dataclass

from app.services.ranking.engine import ComponentName, ProviderMetrics, ScoreBreakdown

# A peer percentile has to reach this to count as a standout: better than 80% of the
# provider's specialty peers.
STANDOUT_PERCENTILE = 0.80
# Distance has no peer percentile (it depends on the search, not the provider), so its
# normalized score stands in: 0.8 means within the nearest fifth of the search radius.
DISTANCE_STANDOUT = 0.80

# Plural nouns for "cheaper than 85% of ___". Unknown specialties fall back to
# "<Name> providers".
_PEER_NOUNS = {
    "cardiology": "cardiologists",
    "orthopedics": "orthopedists",
    "dermatology": "dermatologists",
    "neurology": "neurologists",
    "oncology": "oncologists",
    "primary-care": "primary care doctors",
    "endocrinology": "endocrinologists",
    "gastroenterology": "gastroenterologists",
    "pulmonology": "pulmonologists",
    "psychiatry": "psychiatrists",
}


@dataclass(frozen=True)
class PeerComparison:
    """Where the provider ranks within their specialty, each in [0, 1], 1 = best.

    Used only to choose and phrase the explanation. Scores never see these (volume's
    percentile reaches the score separately, through ProviderMetrics).
    """

    quality: float
    experience: float
    # Higher = cheaper.
    cost: float
    volume: float
    # Plural noun for the peer group, e.g. "cardiologists" (see peer_noun()).
    peers: str


def peer_noun(specialty_slug: str, specialty_name: str) -> str:
    return _PEER_NOUNS.get(specialty_slug, f"{specialty_name} providers")


def explain(breakdown: ScoreBreakdown, metrics: ProviderMetrics, peers: PeerComparison) -> str:
    """E.g. "Stands out for low cost (23% below average; cheaper than 85% of cardiologists).
    15 years of experience, 6.0 miles away."

    The lead names the provider's standout: the factor where they rank highest against
    peers in their own specialty, if that's in the top fifth. It deliberately doesn't use
    the normalized scores. Those are shaped for ranking, not for comparing factors with
    each other: the experience curve saturates early (13 years -> 0.77, while a typical
    quality of 72 -> 0.72), so nearly everyone would "stand out for experience". The
    facts that follow skip whatever the lead already said.
    """
    standout = _standout(breakdown, peers)
    lead = "No single standout factor." if standout is None else _lead(standout, metrics, peers)

    facts = []
    if standout != "experience":
        facts.append(_years_text(metrics.years_experience) + " of experience")
    if metrics.distance_miles is not None and standout != "distance":
        facts.append(_miles_text(metrics.distance_miles))
    if standout != "cost":
        cost = _cost_percent_text(metrics.cost_index)
        facts.append("average cost" if cost is None else f"cost {cost}")
    return f"{lead} {', '.join(facts)}."


def _standout(breakdown: ScoreBreakdown, peers: PeerComparison) -> ComponentName | None:
    candidates: list[tuple[ComponentName, float]] = [
        ("quality", peers.quality),
        ("experience", peers.experience),
        ("cost", peers.cost),
        ("volume", peers.volume),
    ]
    distance = breakdown.component("distance")
    if distance is not None and distance.normalized >= DISTANCE_STANDOUT:
        candidates.append(("distance", distance.normalized))
    # max() keeps the first of equal values, so ties go to the earlier component.
    name, percentile = max(candidates, key=lambda candidate: candidate[1])
    return name if percentile >= STANDOUT_PERCENTILE else None


def _lead(standout: ComponentName, metrics: ProviderMetrics, peers: PeerComparison) -> str:
    match standout:
        case "quality":
            return (
                f"Stands out for a high quality score ({_number(metrics.quality_score)}/100; "
                f"higher than {_percent(peers.quality)} of {peers.peers})."
            )
        case "experience":
            return (
                f"Stands out for experience ({_years_text(metrics.years_experience)}; "
                f"more experienced than {_percent(peers.experience)} of {peers.peers})."
            )
        case "cost":
            # Cheap relative to peers is almost always below average too, but say
            # "about average" rather than print nothing if the index rounds to 0%.
            vs_average = _cost_percent_text(metrics.cost_index) or "about average"
            return (
                f"Stands out for low cost ({vs_average}; "
                f"cheaper than {_percent(peers.cost)} of {peers.peers})."
            )
        case "volume":
            return (
                "Stands out for high patient volume within the specialty "
                f"(busier than {_percent(peers.volume)} of {peers.peers})."
            )
        case "distance":
            assert metrics.distance_miles is not None
            return f"Stands out for being close by ({_miles_text(metrics.distance_miles)})."


def _percent(fraction: float) -> str:
    """Rounded down, so "cheaper than 85%" is never an overstatement. The epsilon keeps
    float noise (0.29 * 100 = 28.999...) from costing a whole point."""
    return f"{math.floor(fraction * 100 + 1e-9)}%"


def _number(value: float) -> str:
    """88.0 -> "88", 73.7 -> "73.7"."""
    return f"{round(value, 1):g}"


def _years_text(years: float) -> str:
    rounded = round(years)
    return f"{rounded} year{'' if rounded == 1 else 's'}"


def _miles_text(miles: float) -> str:
    return f"{miles:.1f} miles away"


def _cost_percent_text(cost_index: float) -> str | None:
    """cost_index 0.9 -> "10% below average"; None when it rounds to 0%."""
    percent = round((cost_index - 1) * 100)
    if percent == 0:
        return None
    direction = "above" if percent > 0 else "below"
    return f"{abs(percent)}% {direction} average"
