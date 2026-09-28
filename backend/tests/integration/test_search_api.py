import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import City, Condition, Provider, SearchLog, Specialty, provider_conditions
from app.repositories.provider_repository import PeerPercentiles, ProviderRepository
from app.repositories.search_log_repository import SearchLogRepository
from app.services.geo import haversine_miles
from tests.helpers import assert_error, count_selects

NYC = {"city": "New York", "state": "NY"}
SEARCH_URL = "/api/v1/search"


def _search(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post(SEARCH_URL, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _all_items(client: TestClient, **body: Any) -> list[dict[str, Any]]:
    """Every result, walking the pages."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        data = _search(client, **body, page=page, page_size=50)
        items += data["items"]
        if page >= data["total_pages"]:
            return items
        page += 1


def _ids(items: list[dict[str, Any]]) -> list[int]:
    return [item["provider"]["id"] for item in items]


def _component(item: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((c for c in item["score"]["components"] if c["name"] == name), None)


def _ids_within(db: Session, city_name: str, state: str, radius: float) -> set[int]:
    city = db.scalars(select(City).where(City.name == city_name, City.state == state)).one()
    return {
        p.id
        for p in db.scalars(select(Provider))
        if haversine_miles(city.latitude, city.longitude, p.latitude, p.longitude) <= radius
    }


# --- Results ----------------------------------------------------------------------------


def test_search_without_location(client: TestClient, seeded_db: Session) -> None:
    data = _search(client)

    assert data["total"] == seeded_db.scalar(select(func.count(Provider.id)))
    assert set(data["weights_used"]) == {"quality", "experience", "cost", "volume"}
    assert sum(data["weights_used"].values()) == pytest.approx(1, abs=0.005)
    for item in data["items"]:
        assert item["distance_miles"] is None
        assert _component(item, "distance") is None
        assert item["explanation"]


def test_search_with_location_keeps_exactly_the_providers_in_radius(
    client: TestClient, seeded_db: Session
) -> None:
    items = _all_items(client, location=NYC, radius_miles=25)

    assert items
    for item in items:
        assert item["distance_miles"] is not None
        assert item["distance_miles"] <= 25
        assert _component(item, "distance") is not None
    # Nobody inside the radius was dropped by the bounding-box prefilter.
    assert set(_ids(items)) == _ids_within(seeded_db, "New York", "NY", 25)


def test_search_location_is_case_insensitive(client: TestClient, seeded_db: Session) -> None:
    lower = _search(client, location={"city": "  new york ", "state": "ny"})

    assert lower == _search(client, location=NYC)


def test_condition_filter(client: TestClient, seeded_db: Session) -> None:
    slug, expected_count = seeded_db.execute(
        select(Condition.slug, func.count())
        .join(provider_conditions, provider_conditions.c.condition_id == Condition.id)
        .group_by(Condition.slug)
        .order_by(func.count().desc(), Condition.slug)
        .limit(1)
    ).one()
    treating = set(
        seeded_db.scalars(
            select(provider_conditions.c.provider_id)
            .join(Condition, Condition.id == provider_conditions.c.condition_id)
            .where(Condition.slug == slug)
        )
    )

    ids = _ids(_all_items(client, condition=slug))

    assert len(ids) == len(set(ids)) == expected_count
    assert set(ids) == treating


def test_minimum_quality_and_experience(client: TestClient, seeded_db: Session) -> None:
    expected = set(
        seeded_db.scalars(
            select(Provider.id).where(Provider.quality_score >= 70, Provider.years_experience >= 10)
        )
    )

    items = _all_items(client, min_quality_score=70, min_years_experience=10)

    assert items
    assert set(_ids(items)) == expected
    for item in items:
        assert item["provider"]["quality_score"] >= 70
        assert item["provider"]["years_experience"] >= 10


def test_require_quality_score_changes_nothing_on_synthetic_data(
    client: TestClient, seeded_db: Session
) -> None:
    # Every synthetic provider has a reported quality score.
    body = {"specialty": "cardiology", "location": NYC}

    assert _all_items(client, **body, require_quality_score=True) == _all_items(client, **body)


@pytest.mark.parametrize(
    ("sort", "value", "descending"),
    [
        ("match", lambda item: item["score"]["overall"], True),
        ("quality", lambda item: item["provider"]["quality_score"], True),
        ("experience", lambda item: item["provider"]["years_experience"], True),
        ("cost", lambda item: item["provider"]["cost_index"], False),
        ("distance", lambda item: item["distance_miles"], False),
    ],
)
def test_sort_options(
    client: TestClient, seeded_db: Session, sort: str, value: Any, descending: bool
) -> None:
    items = _all_items(client, location=NYC, radius_miles=100, sort=sort)
    values = [value(item) for item in items]

    assert len(values) > 5
    assert values == sorted(values, reverse=descending)


def test_pagination_walks_every_result_once(client: TestClient, seeded_db: Session) -> None:
    full = _ids(_all_items(client))
    paged: list[int] = []
    first = _search(client, page_size=7)
    for page in range(1, first["total_pages"] + 1):
        paged += _ids(_search(client, page=page, page_size=7)["items"])

    assert len(paged) == len(set(paged)) == first["total"]
    assert paged == full
    assert _search(client, page=first["total_pages"] + 1, page_size=7)["items"] == []


def test_priority_changes_the_order(client: TestClient, seeded_db: Session) -> None:
    by_quality = _ids(_all_items(client, priority="quality"))
    by_cost = _ids(_all_items(client, priority="cost"))

    assert sorted(by_quality) == sorted(by_cost)
    assert by_quality != by_cost


def test_volume_percentile_does_not_depend_on_filters(
    client: TestClient, seeded_db: Session
) -> None:
    unfiltered = {item["provider"]["id"]: item for item in _all_items(client)}
    filtered = _all_items(client, min_quality_score=72)

    assert 0 < len(filtered) < len(unfiltered)
    for item in filtered:
        assert _component(item, "volume") == _component(
            unfiltered[item["provider"]["id"]], "volume"
        )


# --- Detail scoring ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "params"),
    [
        (
            {"priority": "quality", "location": NYC, "radius_miles": 40},
            {"priority": "quality", "city": "new york", "state": "ny", "radius_miles": 40},
        ),
        *[
            ({"priority": priority, "location": NYC}, {"priority": priority, **NYC})
            for priority in ("balanced", "quality", "cost", "experience", "distance")
        ],
        ({"priority": "cost"}, {"priority": "cost"}),
        ({"priority": "balanced", "specialty": "primary-care"}, {"priority": "balanced"}),
    ],
)
def test_detail_score_and_explanation_match_search_result(
    client: TestClient, seeded_db: Session, body: dict[str, Any], params: dict[str, Any]
) -> None:
    results = _all_items(client, **body)
    assert results

    for result in results:
        response = client.get(f"/api/v1/providers/{result['provider']['id']}", params=params)

        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["score"] == result["score"]
        assert detail["explanation"] == result["explanation"]
        assert detail["distance_miles"] == result["distance_miles"]


def test_explanations_compare_against_specialty_peers(
    client: TestClient, seeded_db: Session
) -> None:
    explanations = [item["explanation"] for item in _all_items(client)]

    peer_phrases = [e for e in explanations if " than " in e and "% of " in e]
    assert peer_phrases, "some provider should stand out against their peers"
    # A filter must not change who someone is compared against: the peer percentiles
    # cover the whole specialty, like the volume percentile.
    filtered = {
        i["provider"]["id"]: i["explanation"] for i in _all_items(client, min_quality_score=72)
    }
    unfiltered = {i["provider"]["id"]: i["explanation"] for i in _all_items(client)}
    assert filtered
    assert all(unfiltered[pid] == text for pid, text in filtered.items())


def test_peer_percentiles_match_their_definition(seeded_db: Session) -> None:
    """percent_rank within the specialty: the share of the other providers this one beats."""
    repository = ProviderRepository(seeded_db)
    providers = seeded_db.scalars(select(Provider)).all()

    def share_beaten(
        provider: Provider, value: Callable[[Provider], float], lower_is_better: bool
    ) -> float:
        peers = [
            p for p in providers if p.specialty_id == provider.specialty_id and p.id != provider.id
        ]
        if not peers:
            return 0.0
        mine = value(provider)
        beaten = [p for p in peers if (value(p) > mine if lower_is_better else value(p) < mine)]
        return len(beaten) / len(peers)

    for provider in providers:
        percentiles = repository.get_peer_percentiles(provider.id)
        assert percentiles is not None
        assert percentiles.quality == pytest.approx(
            share_beaten(provider, lambda p: p.quality_score, False)
        )
        assert percentiles.experience == pytest.approx(
            share_beaten(provider, lambda p: p.years_experience, False)
        )
        assert percentiles.cost == pytest.approx(
            share_beaten(provider, lambda p: p.cost_index, True)
        )
        assert percentiles.volume == pytest.approx(
            share_beaten(provider, lambda p: p.patient_volume, False)
        )


def test_peer_percentiles_do_not_change_scores_or_order(
    client: TestClient, seeded_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The explanation-only percentiles (quality, experience, cost) are inverted here.
    Everything the ranking produces must stay identical; only explanations may change."""
    body = {"location": NYC, "radius_miles": 100}
    searches = [body | {"priority": p} for p in ("balanced", "quality", "cost", "experience")]
    provider_ids = seeded_db.scalars(select(Provider.id).limit(10)).all()

    def ranked_output() -> list[Any]:
        results = [
            [
                (i["provider"]["id"], i["score"], i["distance_miles"])
                for i in _all_items(client, **b)
            ]
            for b in searches
        ]
        details = [
            client.get(f"/api/v1/providers/{pid}", params={"priority": "balanced", **NYC}).json()
            for pid in provider_ids
        ]
        return [results, [(d["score"], d["distance_miles"]) for d in details]]

    def explanations() -> list[str]:
        return [i["explanation"] for i in _all_items(client, **searches[0])]

    before, explained_before = ranked_output(), explanations()

    def invert(percentiles: PeerPercentiles) -> PeerPercentiles:
        return replace(
            percentiles,
            quality=1 - percentiles.quality,
            experience=1 - percentiles.experience,
            cost=1 - percentiles.cost,
        )

    original_candidates = ProviderRepository.search_candidates
    original_single = ProviderRepository.get_peer_percentiles
    monkeypatch.setattr(
        ProviderRepository,
        "search_candidates",
        lambda self, filters: [
            replace(c, percentiles=invert(c.percentiles))
            for c in original_candidates(self, filters)
        ],
    )
    monkeypatch.setattr(
        ProviderRepository,
        "get_peer_percentiles",
        lambda self, provider_id: invert(original_single(self, provider_id)),
    )

    assert ranked_output() == before
    assert explanations() != explained_before


def test_detail_without_priority_has_no_score(client: TestClient, seeded_db: Session) -> None:
    provider_id = seeded_db.scalars(select(Provider.id).limit(1)).one()

    body = client.get(f"/api/v1/providers/{provider_id}", params=NYC).json()

    assert not {"score", "explanation", "distance_miles"} & set(body)


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"priority": "quality", "city": "New York"}, "state"),
        ({"priority": "quality", "state": "NY"}, "state"),
        ({"priority": "quality", "radius_miles": 10}, "radius_miles"),
        ({"priority": "cheapest"}, "priority"),
    ],
)
def test_detail_score_params_are_validated(
    client: TestClient, seeded_db: Session, params: dict[str, Any], field: str
) -> None:
    provider_id = seeded_db.scalars(select(Provider.id).limit(1)).one()

    error = assert_error(
        client.get(f"/api/v1/providers/{provider_id}", params=params), 422, "VALIDATION_ERROR"
    )
    assert [detail["field"] for detail in error["details"]] == [field]


def test_detail_distance_priority_without_location_is_invalid(
    client: TestClient, seeded_db: Session
) -> None:
    provider_id = seeded_db.scalars(select(Provider.id).limit(1)).one()
    url = f"/api/v1/providers/{provider_id}"

    error = assert_error(client.get(url, params={"priority": "distance"}), 422, "INVALID_SEARCH")
    with_location = client.get(url, params={"priority": "distance", **NYC})

    assert error["details"] == [
        {"field": "priority", "message": "priority=distance requires a location"}
    ]
    assert with_location.status_code == 200
    assert _component(with_location.json(), "distance") is not None


@pytest.mark.parametrize("priority", [None, "quality"])
def test_detail_unknown_city(client: TestClient, seeded_db: Session, priority: str | None) -> None:
    provider_id = seeded_db.scalars(select(Provider.id).limit(1)).one()
    params = {"city": "Atlantis", "state": "NY"} | ({"priority": priority} if priority else {})

    error = assert_error(
        client.get(f"/api/v1/providers/{provider_id}", params=params), 422, "LOCATION_NOT_FOUND"
    )
    assert error["details"] == [{"field": "city", "message": "Unknown city"}]


# --- Errors -----------------------------------------------------------------------------


def test_unknown_city(client: TestClient, seeded_db: Session) -> None:
    response = client.post(SEARCH_URL, json={"location": {"city": "Atlantis", "state": "NY"}})

    error = assert_error(response, 422, "LOCATION_NOT_FOUND")
    assert error["details"] == [{"field": "location", "message": "Unknown city"}]


def test_unknown_slugs_are_all_reported(client: TestClient, seeded_db: Session) -> None:
    response = client.post(SEARCH_URL, json={"specialty": "astrology", "condition": "boredom"})

    error = assert_error(response, 422, "INVALID_SEARCH")
    assert {detail["field"] for detail in error["details"]} == {"specialty", "condition"}
    assert "astrology" not in response.text


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"radius_miles": 10}, "radius_miles"),
        ({"surprise": True}, "surprise"),
        ({"page_size": 51}, "page_size"),
        ({"location": {"city": "New York", "state": "NYC"}}, "location.state"),
        ({"location": {"city": "New York"}}, "location.state"),
        ({"radius_miles": 101, "location": NYC}, "radius_miles"),
        ({"priority": "cheapest"}, "priority"),
        ({"sort": "alphabetical"}, "sort"),
        ({"source": "email"}, "source"),
        ({"require_quality_score": "sometimes"}, "require_quality_score"),
    ],
)
def test_invalid_request_is_rejected(
    client: TestClient, seeded_db: Session, body: dict[str, Any], field: str
) -> None:
    error = assert_error(client.post(SEARCH_URL, json=body), 422, "VALIDATION_ERROR")

    assert [detail["field"] for detail in error["details"]] == [field]


@pytest.mark.parametrize(
    ("body", "fields"),
    [
        ({"priority": "distance"}, ["priority"]),
        ({"sort": "distance"}, ["sort"]),
        ({"priority": "distance", "sort": "distance"}, ["priority", "sort"]),
        # Reported together with unknown slugs, not one at a time.
        ({"sort": "distance", "specialty": "astrology"}, ["sort", "specialty"]),
    ],
)
def test_distance_without_location_is_invalid(
    client: TestClient, seeded_db: Session, body: dict[str, Any], fields: list[str]
) -> None:
    error = assert_error(client.post(SEARCH_URL, json=body), 422, "INVALID_SEARCH")

    assert [detail["field"] for detail in error["details"]] == fields
    assert error["details"][0]["message"] == f"{fields[0]}=distance requires a location"
    assert seeded_db.scalars(select(SearchLog)).all() == []


def test_distance_with_location_is_fine(client: TestClient, seeded_db: Session) -> None:
    data = _search(client, priority="distance", sort="distance", location=NYC)

    assert data["weights_used"]["distance"] == 0.5
    assert data["total"] > 0


# --- Logging ----------------------------------------------------------------------------


def test_search_writes_a_log_row(
    client: TestClient, seeded_db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.search_service")
    cardiology_id = seeded_db.scalars(
        select(Specialty.id).where(Specialty.slug == "cardiology")
    ).one()

    data = _search(
        client,
        specialty="cardiology",
        condition="heart-failure",
        location=NYC,
        radius_miles=100,
        priority="cost",
        source="nl",
    )

    [row] = seeded_db.scalars(select(SearchLog)).all()
    assert row.source == "nl"
    assert row.parser_used is None
    assert row.specialty_id == cardiology_id
    assert row.state == "NY"
    assert row.priority == "cost"
    assert row.result_count == data["total"]
    assert row.latency_ms > 0
    [record] = [r for r in caplog.records if r.getMessage() == "search"]
    assert record.result_count == data["total"]
    # Health details stay out of the log line, like the table.
    assert "heart-failure" not in str(record.__dict__)
    assert "New York" not in str(record.__dict__)


def test_search_logs_table_has_no_free_text_columns() -> None:
    assert set(SearchLog.__table__.columns.keys()) == {
        "id",
        "created_at",
        "source",
        "parser_used",
        "specialty_id",
        "state",
        "priority",
        "result_count",
        "latency_ms",
    }


def test_rejected_search_writes_no_log_row(client: TestClient, seeded_db: Session) -> None:
    client.post(SEARCH_URL, json={"specialty": "astrology"})

    assert seeded_db.scalars(select(SearchLog)).all() == []


def test_log_write_failure_does_not_fail_the_search(
    client: TestClient,
    seeded_db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original_add = SearchLogRepository.add

    def add_invalid_row(self: SearchLogRepository, **fields: Any) -> None:
        # Violates the source CHECK constraint, so the real INSERT fails and rolls back.
        original_add(self, **(fields | {"source": "bogus"}))

    monkeypatch.setattr(SearchLogRepository, "add", add_invalid_row)

    data = _search(client)

    assert data["total"] > 0
    assert seeded_db.scalars(select(SearchLog)).all() == []
    assert any(
        r.levelno == logging.WARNING and "search_logs" in r.getMessage() for r in caplog.records
    )


# --- Queries ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"page_size": 50},
        {
            "specialty": "primary-care",
            "condition": "hypertension",
            "location": NYC,
            "radius_miles": 100,
            "page_size": 50,
        },
    ],
)
def test_search_uses_a_constant_number_of_queries(
    client: TestClient, seeded_db: Session, db_engine: Engine, body: dict[str, Any]
) -> None:
    with count_selects(db_engine) as statements:
        _search(client, **body)

    # Up to: the has-conditions check, specialty, condition and city lookups, plus one
    # candidates query.
    assert 1 <= len(statements) <= 5, statements


# --- Cities -----------------------------------------------------------------------------


def test_cities_lists_the_seeded_cities(client: TestClient, seeded_db: Session) -> None:
    response = client.get("/api/v1/cities")

    assert response.status_code == 200
    cities = response.json()
    assert len(cities) == seeded_db.scalar(select(func.count(City.id)))
    assert set(cities[0]) == {"city", "state"}
    assert [(c["state"], c["city"]) for c in cities] == sorted(
        (c["state"], c["city"]) for c in cities
    )
    assert NYC in cities


def test_every_listed_city_works_as_a_search_location(
    client: TestClient, seeded_db: Session
) -> None:
    for location in client.get("/api/v1/cities").json():
        response = client.post(SEARCH_URL, json={"location": location, "page_size": 1})

        assert response.status_code == 200, location
