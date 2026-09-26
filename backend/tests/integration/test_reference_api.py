from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Condition, Provider, Specialty, provider_conditions
from tests.helpers import assert_error


def test_specialties_lists_all_with_provider_counts(client: TestClient, seeded_db: Session) -> None:
    response = client.get("/api/v1/specialties")

    assert response.status_code == 200
    specialties = response.json()
    assert len(specialties) == 10
    assert set(specialties[0]) == {"id", "slug", "name", "provider_count"}
    names = [s["name"] for s in specialties]
    assert names == sorted(names)
    total_providers = seeded_db.scalar(select(func.count(Provider.id)))
    assert sum(s["provider_count"] for s in specialties) == total_providers


def test_conditions_without_specialty_lists_all(client: TestClient, seeded_db: Session) -> None:
    response = client.get("/api/v1/conditions")

    assert response.status_code == 200
    conditions = response.json()
    assert len(conditions) == seeded_db.scalar(select(func.count(Condition.id)))
    assert set(conditions[0]) == {"id", "slug", "name"}
    names = [c["name"] for c in conditions]
    assert names == sorted(names)


def test_conditions_filtered_by_specialty(client: TestClient, seeded_db: Session) -> None:
    treated_by_cardiologists = set(
        seeded_db.scalars(
            select(Condition.slug)
            .join(provider_conditions, provider_conditions.c.condition_id == Condition.id)
            .join(Provider, Provider.id == provider_conditions.c.provider_id)
            .join(Specialty, Specialty.id == Provider.specialty_id)
            .where(Specialty.slug == "cardiology")
        )
    )
    assert treated_by_cardiologists  # the seed data must have some for this test to mean much

    response = client.get("/api/v1/conditions", params={"specialty": "cardiology"})

    assert response.status_code == 200
    slugs = [c["slug"] for c in response.json()]
    assert set(slugs) == treated_by_cardiologists
    assert len(slugs) == len(set(slugs))
    assert "acne" not in slugs


def test_conditions_unknown_specialty_returns_404(client: TestClient, seeded_db: Session) -> None:
    response = client.get("/api/v1/conditions", params={"specialty": "astrology"})

    assert_error(response, 404, "NOT_FOUND")
