"""Show how the ranking engine trades off three made-up providers under each priority.

No database. Run from backend/:  python -m scripts.ranking_demo
"""

from app.services.explanation import PeerComparison, explain
from app.services.ranking.engine import ProviderMetrics, rank, score_provider
from app.services.ranking.weights import Priority, get_weights

RADIUS_MILES = 20.0

PROVIDERS = {
    "Excellent but expensive": ProviderMetrics(
        provider_id=1,
        quality_score=95,
        years_experience=24,
        cost_index=1.45,
        volume_percentile=0.85,
        distance_miles=15.0,
    ),
    "Cheap but average": ProviderMetrics(
        provider_id=2,
        quality_score=70,
        years_experience=12,
        cost_index=0.60,
        volume_percentile=0.50,
        distance_miles=10.0,
    ),
    "Close but junior": ProviderMetrics(
        provider_id=3,
        quality_score=78,
        years_experience=2,
        cost_index=1.00,
        volume_percentile=0.20,
        distance_miles=1.0,
    ),
}

# Made-up ranks among each provider's specialty peers (1 = best; for cost, 1 = cheapest).
# In the app these come from the database. They only shape the explanations: the scores
# and ranks above are computed without them.
PEERS = {
    "Excellent but expensive": PeerComparison(
        quality=0.97, experience=0.88, cost=0.04, volume=0.85, peers="cardiologists"
    ),
    "Cheap but average": PeerComparison(
        quality=0.45, experience=0.52, cost=0.93, volume=0.50, peers="cardiologists"
    ),
    "Close but junior": PeerComparison(
        quality=0.66, experience=0.05, cost=0.48, volume=0.20, peers="cardiologists"
    ),
}


def main() -> None:
    names = {metrics.provider_id: name for name, metrics in PROVIDERS.items()}
    results = {priority: rank(PROVIDERS.values(), priority, RADIUS_MILES) for priority in Priority}

    print(f"Overall score (rank) per priority, {RADIUS_MILES:.0f}-mile radius\n")
    name_width = max(len(name) for name in PROVIDERS) + 2
    print(f"{'Provider':<{name_width}}" + "".join(f"{p.value:>14}" for p in Priority))
    for name, metrics in PROVIDERS.items():
        cells = []
        for priority in Priority:
            position, (_, breakdown) = next(
                (i, item)
                for i, item in enumerate(results[priority], start=1)
                if item[0].provider_id == metrics.provider_id
            )
            cells.append(f"{breakdown.overall:>9.1f} (#{position})")
        print(f"{name:<{name_width}}" + "".join(cells))

    print("\nTop provider per priority:")
    for priority, ranked in results.items():
        print(f"  {priority.value:<12}{names[ranked[0][0].provider_id]}")

    name, metrics = "Cheap but average", PROVIDERS["Cheap but average"]
    breakdown = score_provider(metrics, get_weights(Priority.BALANCED), RADIUS_MILES)
    print(f"\nBreakdown for {name!r}, priority=balanced:\n")
    print(f"  {'component':<12}{'raw':>8}{'normalized':>12}{'weight':>9}{'points':>9}")
    for c in breakdown.components:
        print(
            f"  {c.name:<12}{c.raw:>8.2f}{c.normalized:>12.3f}"
            f"{c.weight:>9.2f}{c.contribution:>9.2f}"
        )
    print(f"  {'overall':<12}{'':>29}{breakdown.overall:>9.2f}")

    # The explanation leads with each provider's standout (where they rank highest among
    # specialty peers), which doesn't depend on the priority, so one priority is enough.
    print("\nExplanations:")
    weights = get_weights(Priority.BALANCED)
    for name, metrics in PROVIDERS.items():
        text = explain(score_provider(metrics, weights, RADIUS_MILES), metrics, PEERS[name])
        print(f"  {name + ':':<{name_width}}{text}")


if __name__ == "__main__":
    main()
