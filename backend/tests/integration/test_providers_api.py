import math

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import Provider, Specialty
from tests.helpers import assert_error, count_selects

SUMMARY_FIELDS = {
    "id",
    "display_name",
    "specialty",
    "subspecialty",
    "city",
    "state",
    "years_experience",
    "quality_score",
    "cost_index",
    "accepting_new_patients",
}
DETAIL_FIELDS = SUMMARY_FIELDS | {
    "zip_code",
    "latitude",
    "longitude",
    "patient_volume",
    "complication_rate",
    "readmission_rate",
    "conditions",
}


def _all_ids(client: TestClient, **params: object) -> list[int]:
    response = client.get("/api/v1/providers", params={"page_size": 100, **params})
    assert response.status_code == 200
    assert response.json()["total_pages"] <= 1, "seed data outgrew one page; paginate here"
    return [item["id"] for item in response.json()["items"]]


def test_list_providers_paginates(client: TestClient, seeded_db: Session) -> None:
    total = seeded_db.scalar(select(func.count(Provider.id)))

    response = client.get("/api/v1/providers", params={"page_size": 5})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 5
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == total
    assert body["total_pages"] == math.ceil(total / 5)
    item = body["items"][0]
    assert set(item) == SUMMARY_FIELDS
    assert set(item["specialty"]) == {"slug", "name"}
    assert item["display_name"].startswith("Dr. ")
    assert item["display_name"].endswith((", MD", ", DO"))


def test_list_providers_page_past_end_is_empty(client: TestClient, seeded_db: Session) -> None:
    for page in (100, 10**12):
        response = client.get("/api/v1/providers", params={"page": page})

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] > 0


def test_list_providers_rejects_bad_paging(client: TestClient) -> None:
    error = assert_error(
        client.get("/api/v1/providers", params={"page_size": 101}), 422, "VALIDATION_ERROR"
    )
    assert error["details"][0]["field"] == "page_size"

    assert_error(client.get("/api/v1/providers", params={"page": 0}), 422, "VALIDATION_ERROR")


def test_list_providers_order_is_deterministic(client: TestClient, seeded_db: Session) -> None:
    expected = list(
        seeded_db.scalars(
            select(Provider.id).order_by(Provider.last_name, Provider.first_name, Provider.id)
        )
    )

    assert _all_ids(client) == expected
    assert _all_ids(client) == expected
    paged: list[int] = []
    for page in range(1, math.ceil(len(expected) / 7) + 1):
        response = client.get("/api/v1/providers", params={"page": page, "page_size": 7})
        paged += [item["id"] for item in response.json()["items"]]
    assert paged == expected


def test_list_providers_filters_by_specialty(client: TestClient, seeded_db: Session) -> None:
    expected = seeded_db.scalar(
        select(func.count(Provider.id)).join(Specialty).where(Specialty.slug == "primary-care")
    )

    response = client.get(
        "/api/v1/providers", params={"specialty": "primary-care", "page_size": 100}
    )

    body = response.json()
    assert body["total"] == expected > 0
    assert {item["specialty"]["slug"] for item in body["items"]} == {"primary-care"}


def test_list_providers_unknown_specialty_returns_404(
    client: TestClient, seeded_db: Session
) -> None:
    assert_error(
        client.get("/api/v1/providers", params={"specialty": "astrology"}), 404, "NOT_FOUND"
    )


def test_list_providers_state_filter_is_case_insensitive(
    client: TestClient, seeded_db: Session
) -> None:
    state = seeded_db.scalars(select(Provider.state).limit(1)).one()

    upper = client.get("/api/v1/providers", params={"state": state.upper(), "page_size": 100})
    lower = client.get("/api/v1/providers", params={"state": state.lower(), "page_size": 100})

    assert upper.json() == lower.json()
    assert upper.json()["total"] > 0
    assert {item["state"] for item in upper.json()["items"]} == {state}


def test_list_providers_rejects_invalid_state(client: TestClient) -> None:
    for state in ("N", "NYC", "N1"):
        assert_error(
            client.get("/api/v1/providers", params={"state": state}), 422, "VALIDATION_ERROR"
        )


def test_list_providers_filters_by_city_and_accepting(
    client: TestClient, seeded_db: Session
) -> None:
    city = seeded_db.scalars(select(Provider.city).limit(1)).one()

    by_city = client.get("/api/v1/providers", params={"city": city.upper(), "page_size": 100})
    accepting = _all_ids(client, accepting_new_patients=True)
    not_accepting = _all_ids(client, accepting_new_patients=False)

    assert by_city.json()["total"] > 0
    assert {item["city"] for item in by_city.json()["items"]} == {city}
    assert sorted(accepting + not_accepting) == sorted(_all_ids(client))
    assert accepting and not_accepting


def test_list_providers_avoids_n_plus_one(
    client: TestClient, seeded_db: Session, db_engine: Engine
) -> None:
    with count_selects(db_engine) as statements:
        response = client.get("/api/v1/providers", params={"page_size": 20})

    assert len(response.json()["items"]) == 20
    # A count query and one page query (specialty joined in), however many rows.
    assert 1 <= len(statements) <= 3, statements


def test_get_provider_returns_detail_with_conditions(
    client: TestClient, seeded_db: Session, db_engine: Engine
) -> None:
    provider = seeded_db.scalars(select(Provider).limit(1)).one()
    expected_slugs = {c.slug for c in provider.conditions}
    seeded_db.expunge_all()

    with count_selects(db_engine) as statements:
        response = client.get(f"/api/v1/providers/{provider.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == provider.id
    assert {c["slug"] for c in body["conditions"]} == expected_slugs
    names = [c["name"] for c in body["conditions"]]
    assert names == sorted(names)
    assert len(statements) <= 3, statements


def test_get_provider_missing_returns_404(client: TestClient, seeded_db: Session) -> None:
    missing_id = (seeded_db.scalar(select(func.max(Provider.id))) or 0) + 1

    assert_error(client.get(f"/api/v1/providers/{missing_id}"), 404, "NOT_FOUND")


def test_get_provider_rejects_invalid_ids(client: TestClient) -> None:
    for provider_id in ("0", "-1", "abc", str(2**31)):
        assert_error(client.get(f"/api/v1/providers/{provider_id}"), 422, "VALIDATION_ERROR")
