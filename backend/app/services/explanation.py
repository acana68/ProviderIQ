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
class Wording:
    """The phrases that depend on what the dataset's numbers mean."""

    # "Stands out for high ___ within the specialty"
    volume: str
    # The lead when cost_index is the standout. Placeholders: {vs_baseline} (e.g. "12%
    # below average"), {percent} (share of peers beaten) and {peers}.
    cost_lead: str
    # The fact about cost_index otherwise, with {vs_baseline}.
    cost_fact: str
    # What cost_index 1.0 is: "12% below ___"
    cost_baseline: str
    # The fact when the index rounds to the baseline.
    typical_cost: str
    # The fact when the index is imputed.
    cost_not_reported: str


SYNTHETIC_WORDING = Wording(
    volume="patient volume",
    cost_lead="Stands out for low cost ({vs_baseline}; cheaper than {percent} of {peers}).",
    cost_fact="cost {vs_baseline}",
    cost_baseline="average",
    typical_cost="average cost",
    cost_not_reported="cost not reported",
)
# CMS volume counts Medicare patients only. Its cost_index is Medicare spending per
# patient relative to the NJ specialty median: not a price, so never called "cost".
CMS_WORDING = Wording(
    volume="Medicare patient volume",
    cost_lead=(
        "Stands out for lower Medicare spending per patient (lower than {percent} of {peers})."
    ),
    cost_fact="Medicare spending per patient {vs_baseline}",
    cost_baseline="the specialty median",
    typical_cost="Medicare spending per patient near the specialty median",
    cost_not_reported="Medicare spending per patient not reported",
)


@dataclass(frozen=True)
class PeerComparison:
    """Where the provider ranks within their specialty, each in [0, 1], 1 = best.

    Used only to choose and phrase the explanation. Scores never see these (volume's
    percentile reaches the score separately, through ProviderMetrics). None: the
    provider doesn't have that metric.
    """

    quality: float | None
    experience: float | None
    # Higher = cheaper.
    cost: float | None
    volume: float
    # Plural noun for the peer group, e.g. "cardiologists" (see peer_noun()).
    peers: str
    wording: Wording = SYNTHETIC_WORDING


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

    An imputed value is never a standout (it's a stand-in, not an achievement), and the
    facts say it wasn't reported instead of quoting the stand-in.
    """
    standout = _standout(breakdown, metrics, peers)
    lead = "No single standout factor." if standout is None else _lead(standout, metrics, peers)

    facts = []
    if metrics.quality_imputed:
        facts.append("quality score not reported")
    if metrics.experience_imputed:
        facts.append("experience not reported")
    elif standout != "experience":
        facts.append(_years_text(metrics.years_experience) + " of experience")
    if metrics.distance_miles is not None and standout != "distance":
        facts.append(_miles_text(metrics.distance_miles))
    if metrics.cost_imputed:
        facts.append(peers.wording.cost_not_reported)
    elif standout != "cost":
        cost = _cost_percent_text(metrics.cost_index, peers.wording)
        facts.append(
            peers.wording.typical_cost
            if cost is None
            else peers.wording.cost_fact.format(vs_baseline=cost)
        )
    text = ", ".join(facts)
    return f"{lead} {text[0].upper()}{text[1:]}."


def _standout(
    breakdown: ScoreBreakdown, metrics: ProviderMetrics, peers: PeerComparison
) -> ComponentName | None:
    # An imputed value is left out whatever its percentile says (the flags are checked,
    # not only a missing percentile): a stand-in can't make a provider stand out.
    candidates: list[tuple[ComponentName, float | None]] = [
        ("quality", None if metrics.quality_imputed else peers.quality),
        ("experience", None if metrics.experience_imputed else peers.experience),
        ("cost", None if metrics.cost_imputed else peers.cost),
        ("volume", peers.volume),
    ]
    distance = breakdown.component("distance")
    if distance is not None and distance.normalized >= DISTANCE_STANDOUT:
        candidates.append(("distance", distance.normalized))
    present = [(name, value) for name, value in candidates if value is not None]
    # max() keeps the first of equal values, so ties go to the earlier component.
    name, percentile = max(present, key=lambda candidate: candidate[1])
    return name if percentile >= STANDOUT_PERCENTILE else None


def _lead(standout: ComponentName, metrics: ProviderMetrics, peers: PeerComparison) -> str:
    match standout:
        case "quality":
            # _standout() only picks a metric the provider has.
            assert peers.quality is not None
            return (
                f"Stands out for a high quality score ({_number(metrics.quality_score)}/100; "
                f"higher than {_percent(peers.quality)} of {peers.peers})."
            )
        case "experience":
            assert peers.experience is not None
            return (
                f"Stands out for experience ({_years_text(metrics.years_experience)}; "
                f"more experienced than {_percent(peers.experience)} of {peers.peers})."
            )
        case "cost":
            assert peers.cost is not None
            # Cheap relative to peers is almost always below average too, but say
            # "about average" rather than print nothing if the index rounds to 0%.
            vs_baseline = (
                _cost_percent_text(metrics.cost_index, peers.wording)
                or f"about {peers.wording.cost_baseline}"
            )
            return peers.wording.cost_lead.format(
                vs_baseline=vs_baseline, percent=_percent(peers.cost), peers=peers.peers
            )
        case "volume":
            return (
                f"Stands out for high {peers.wording.volume} within the specialty "
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


def _cost_percent_text(cost_index: float, wording: Wording) -> str | None:
    """cost_index 0.9 -> "10% below average"; None when it rounds to 0%."""
    percent = round((cost_index - 1) * 100)
    if percent == 0:
        return None
    direction = "above" if percent > 0 else "below"
    return f"{abs(percent)}% {direction} {wording.cost_baseline}"
