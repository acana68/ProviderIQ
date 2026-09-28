"""Measure POST /search latency in-process: the whole request path (validation, the SQL,
ranking, serialization, the search log) without the network, nginx or rate limits.

Writes nothing: each request runs in a transaction that is rolled back afterwards.
Uses DATABASE_URL, so it measures whichever dataset is seeded there.

Run from backend/:
    python -m scripts.bench_search                  # worst case: no filters, every provider
    python -m scripts.bench_search --requests 500 --body '{"specialty": "cardiology"}'
"""

import argparse
import json
import statistics
import time
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--body", default="{}", help="search request JSON (default: {})")
    args = parser.parse_args()
    body = json.loads(args.body)

    settings = get_settings().model_copy(
        update={
            "rate_limit_per_minute": 1_000_000,
            "log_level": "WARNING",
            # Search never calls the model; don't build a client for it either.
            "ai_provider": "none",
            "anthropic_api_key": None,
        }
    )
    app = create_app(settings)
    engine = app.state.db_engine

    def rolled_back_session() -> Iterator[Session]:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()

    app.dependency_overrides[get_db] = rolled_back_session

    with TestClient(app) as client:
        dataset = client.get(f"{settings.api_prefix}/dataset").json().get("source")
        total = None
        timings_ms = []
        for i in range(args.warmup + args.requests):
            start = time.perf_counter()
            response = client.post(f"{settings.api_prefix}/search", json=body)
            elapsed = (time.perf_counter() - start) * 1000
            if response.status_code != 200:
                raise SystemExit(f"search failed: HTTP {response.status_code} {response.text}")
            total = response.json()["total"]
            if i >= args.warmup:
                timings_ms.append(elapsed)

    cuts = statistics.quantiles(timings_ms, n=100)
    print(f"dataset {dataset}: {total:,} providers matched, {args.requests} requests")
    print(
        f"  p50 {cuts[49]:.1f} ms   p95 {cuts[94]:.1f} ms   p99 {cuts[98]:.1f} ms   "
        f"max {max(timings_ms):.1f} ms   mean {statistics.fmean(timings_ms):.1f} ms"
    )


if __name__ == "__main__":
    main()
