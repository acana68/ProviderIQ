from dataclasses import replace

import pytest

from app.services.explanation import CMS_WORDING, PeerComparison, explain, peer_noun
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

# 12 of 20 miles: normalized distance 0.4, far from a standout.
PLAIN = ProviderMetrics(
    provider_id=2,
    quality_score=50,
    years_experience=3,
    cost_index=1.0,
    volume_percentile=0.5,
    distance_miles=12.0,
)

# Middle of the pack on everything.
AVERAGE_PEERS = PeerComparison(
    quality=0.5, experience=0.5, cost=0.5, volume=0.5, peers="cardiologists"
)


def _explain(
    metrics: ProviderMetrics,
    peers: PeerComparison = AVERAGE_PEERS,
    priority: Priority = Priority.QUALITY,
    radius_miles: float | None = 20,
) -> str:
    breakdown = score_provider(metrics, get_weights(priority), radius_miles)
    return explain(breakdown, metrics, peers)


def test_documented_example() -> None:
    peers = replace(AVERAGE_PEERS, quality=0.92)

    assert _explain(DOCUMENTED, peers) == (
        "Stands out for a high quality score (88/100; higher than 92% of cardiologists). "
        "15 years of experience, 6.0 miles away, cost 10% below average."
    )


@pytest.mark.parametrize(
    ("metric_changes", "peer_changes", "expected"),
    [
        (
            {"quality_score": 73.7},
            {"quality": 0.85},
            "Stands out for a high quality score (73.7/100; higher than 85% of cardiologists). "
            "3 years of experience, 12.0 miles away, average cost.",
        ),
        (
            {"years_experience": 25},
            {"experience": 0.9},
            "Stands out for experience (25 years; more experienced than 90% of cardiologists). "
            "12.0 miles away, average cost.",
        ),
        (
            {"cost_index": 0.77},
            {"cost": 0.85},
            "Stands out for low cost (23% below average; cheaper than 85% of cardiologists). "
            "3 years of experience, 12.0 miles away.",
        ),
        (
            {"volume_percentile": 0.8},
            {"volume": 0.8},
            "Stands out for high patient volume within the specialty "
            "(busier than 80% of cardiologists). 3 years of experience, 12.0 miles away, "
            "average cost.",
        ),
        (
            {"distance_miles": 2.1},
            {},
            "Stands out for being close by (2.1 miles away). 3 years of experience, average cost.",
        ),
    ],
)
def test_leads_with_the_standout_and_skips_its_repeat(
    metric_changes: dict[str, float], peer_changes: dict[str, float], expected: str
) -> None:
    peers = replace(AVERAGE_PEERS, **peer_changes)

    assert _explain(replace(PLAIN, **metric_changes), peers) == expected


def test_saturated_experience_curve_does_not_make_a_standout() -> None:
    # The bug this design fixes: 13 years normalizes to 0.77, above a quality of 72
    # (0.72), yet 13 years is below average for the specialty.
    metrics = replace(PLAIN, quality_score=72, years_experience=13)
    breakdown = score_provider(metrics, get_weights(Priority.BALANCED), 20)
    experience = breakdown.component("experience")
    assert experience is not None and experience.normalized > 0.76

    text = explain(breakdown, metrics, replace(AVERAGE_PEERS, experience=0.4))

    assert text.startswith("No single standout factor.")


def test_highest_peer_percentile_wins() -> None:
    peers = replace(AVERAGE_PEERS, quality=0.82, cost=0.95, experience=0.88)

    assert _explain(PLAIN, peers).startswith("Stands out for low cost")


def test_tie_goes_to_the_earlier_component() -> None:
    peers = replace(AVERAGE_PEERS, quality=0.9, volume=0.9)

    assert _explain(PLAIN, peers).startswith("Stands out for a high quality score")


def test_threshold_is_80th_percentile_inclusive() -> None:
    assert _explain(PLAIN, replace(AVERAGE_PEERS, cost=0.8)).startswith("Stands out for low cost")
    assert _explain(PLAIN, replace(AVERAGE_PEERS, cost=0.79)).startswith("No single standout")


@pytest.mark.parametrize(
    ("distance_miles", "peer_quality", "lead"),
    [
        # 4 of 20 miles normalizes to exactly 0.8: a standout.
        (4.0, 0.5, "Stands out for being close by"),
        # 4.2 miles normalizes to 0.79: not close enough.
        (4.2, 0.5, "No single standout"),
        # 1 mile (0.95) beats a peer percentile of 0.9...
        (1.0, 0.9, "Stands out for being close by"),
        # ...but not 0.96.
        (1.0, 0.96, "Stands out for a high quality score"),
    ],
)
def test_distance_uses_its_normalized_score(
    distance_miles: float, peer_quality: float, lead: str
) -> None:
    metrics = replace(PLAIN, distance_miles=distance_miles)

    assert _explain(metrics, replace(AVERAGE_PEERS, quality=peer_quality)).startswith(lead)


def test_standout_does_not_depend_on_priority() -> None:
    peers = replace(AVERAGE_PEERS, cost=0.9)
    metrics = replace(PLAIN, cost_index=0.7, distance_miles=6.0)
    leads = {_explain(metrics, peers, priority).split(".")[0] for priority in Priority}

    assert leads == {
        "Stands out for low cost (30% below average; cheaper than 90% of cardiologists)"
    }


def test_without_location_omits_distance() -> None:
    text = _explain(replace(DOCUMENTED, distance_miles=None), radius_miles=None)

    assert "miles" not in text
    assert text == "No single standout factor. 15 years of experience, cost 10% below average."


def test_percentages_round_down() -> None:
    # 85.9% would round up to "86%", overstating it; 0.29 * 100 is 28.999... in floats.
    text = _explain(PLAIN, replace(AVERAGE_PEERS, cost=0.859))
    assert "cheaper than 85% of" in text

    text = _explain(PLAIN, replace(AVERAGE_PEERS, quality=0.29, cost=0.81))
    assert "cheaper than 81% of" in text


def test_cheap_among_peers_but_average_index() -> None:
    text = _explain(replace(PLAIN, cost_index=0.998), replace(AVERAGE_PEERS, cost=0.9))

    assert text.startswith("Stands out for low cost (about average; cheaper than 90% of")


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
def test_cost_wording_in_the_facts(cost_index: float, wording: str) -> None:
    assert _explain(replace(DOCUMENTED, cost_index=cost_index)).endswith(f"{wording}.")


def test_singular_year() -> None:
    assert "1 year of experience" in _explain(replace(DOCUMENTED, years_experience=1))


def test_peer_noun() -> None:
    assert peer_noun("cardiology", "Cardiology") == "cardiologists"
    assert peer_noun("primary-care", "Primary Care") == "primary care doctors"
    assert peer_noun("sleep-medicine", "Sleep Medicine") == "Sleep Medicine providers"


# --- Imputed values ----------------------------------------------------------------------


@pytest.mark.parametrize("percentile", [0.95, 1.0])
def test_an_imputed_quality_is_never_a_standout(percentile: float) -> None:
    """Even if a percentile slipped through: the metrics' own flag decides."""
    metrics = replace(PLAIN, quality_score=95, quality_imputed=True)

    text = _explain(metrics, replace(AVERAGE_PEERS, quality=percentile))

    assert "quality score (" not in text
    assert text == (
        "No single standout factor. Quality score not reported, 3 years of experience, "
        "12.0 miles away, average cost."
    )


def test_an_imputed_experience_is_never_a_standout_nor_quoted() -> None:
    metrics = replace(PLAIN, years_experience=30, experience_imputed=True)

    text = _explain(metrics, replace(AVERAGE_PEERS, experience=0.99))

    assert text == (
        "No single standout factor. Experience not reported, 12.0 miles away, average cost."
    )


def test_a_missing_percentile_is_skipped_and_the_next_best_standout_wins() -> None:
    metrics = replace(PLAIN, quality_imputed=True)
    peers = replace(AVERAGE_PEERS, quality=None, volume=0.9)

    assert _explain(metrics, peers).startswith(
        "Stands out for high patient volume within the specialty (busier than 90% of"
    )


def test_cms_wording_calls_the_index_medicare_spending_per_patient() -> None:
    cms = replace(AVERAGE_PEERS, wording=CMS_WORDING)
    low_spender = _explain(replace(PLAIN, cost_index=0.77), replace(cms, cost=0.85))
    typical = _explain(PLAIN, cms)
    high_spender = _explain(replace(PLAIN, cost_index=1.3), cms)
    busy = _explain(PLAIN, replace(cms, volume=0.95))

    assert low_spender.startswith(
        "Stands out for lower Medicare spending per patient (lower than 85% of cardiologists)."
    )
    assert typical.endswith("Medicare spending per patient near the specialty median.")
    assert high_spender.endswith("Medicare spending per patient 30% above the specialty median.")
    assert busy.startswith("Stands out for high Medicare patient volume")
    # CMS spending isn't a price: never "cost", "cheaper" or "price".
    for text in (low_spender, typical, high_spender, busy):
        assert not {"cost", "cheaper", "price"} & set(text.lower().replace(",", " ").split())


def test_unreported_spending_is_never_a_standout() -> None:
    metrics = replace(PLAIN, cost_imputed=True)
    # The imputed index has no percentile; even a high one passed in is ignored.
    peers = replace(AVERAGE_PEERS, cost=0.99, wording=CMS_WORDING)

    assert _explain(metrics, peers) == (
        "No single standout factor. 3 years of experience, 12.0 miles away, "
        "Medicare spending per patient not reported."
    )
