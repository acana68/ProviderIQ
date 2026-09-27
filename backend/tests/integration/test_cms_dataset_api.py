"""The API on a database seeded with CMS data: GET /dataset, imputed and not-reported
metrics, and conditions being unavailable. The data comes from running the pipeline on
the fake raw files in tests/fixtures/cms_raw/ (see its README for each NPI)."""

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DatasetMetadata, Provider
from pipeline.transform import run
from scripts.generate_data import REFERENCE_DIR
from scripts.seed_db import seed
from tests.helpers import assert_error

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cms_raw"
SEARCH_URL = "/api/v1/search"
MANIFEST = {
    "sources": {
        "ndf": {"downloaded_at": "2026-09-27T09:00:00+00:00", "modified": "2026-08-18"},
        "mips": {"downloaded_at": "2026-09-26T09:00:00+00:00", "version": "Performance Year 2024"},
        "physician": {
            "downloaded_at": "2026-09-27T09:00:00+00:00",
            "version": "Calendar Year 2024",
        },
    }
}
# 9000000002 and 9000000011 have no MIPS score; the others score 80.5 and 65.
CARDIOLOGY_QUALITY_MEDIAN = (80.5 + 65) / 2


@pytest.fixture
def cms_data_dir(db_session: Session, tmp_path: Path) -> Path:
    """A data/ layout with the reference specialties and the pipeline's CMS output."""
    run(db_session.connection(), raw_dir=FIXTURE_DIR, out_dir=tmp_path / "cms", reference_year=2026)
    (tmp_path / "cms" / "MANIFEST.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    shutil.copytree(REFERENCE_DIR, tmp_path / "reference")
    return tmp_path


@pytest.fixture
def cms_db(db_session: Session, cms_data_dir: Path) -> Session:
    seed(db_session, cms_data_dir, "cms_nj")
    db_session.expunge_all()
    return db_session


def _id(session: Session, npi: str) -> int:
    return session.scalars(select(Provider.id).where(Provider.npi == npi)).one()


def _search(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post(SEARCH_URL, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _by_npi(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["provider"]["npi"]: item for item in body["items"]}


def test_seed_loads_cms_data_without_conditions(db_session: Session, cms_data_dir: Path) -> None:
    counts = seed(db_session, cms_data_dir, "cms_nj")

    assert counts == {
        "specialties": 10,
        "conditions": 0,
        "cities": 3,
        "providers": 8,
        "provider_conditions": 0,
    }
    metadata = db_session.get(DatasetMetadata, 1)
    assert metadata is not None
    assert metadata.source == "cms_nj"
    # The earliest download of the three CMS files.
    assert metadata.as_of == date(2026, 9, 26)
    assert metadata.vintage is not None and "Performance Year 2024" in metadata.vintage


def test_seeded_rows_keep_missing_values_null(cms_db: Session) -> None:
    provider = cms_db.get(Provider, _id(cms_db, "9000000002"))

    assert provider is not None
    assert provider.data_source == "cms"
    assert provider.quality_score is None
    assert provider.quality_imputed is True
    assert provider.complication_rate is None
    assert provider.readmission_rate is None
    # Unknown, not quietly true.
    assert provider.accepting_new_patients is None


def test_dataset_endpoint_describes_cms_data(client: TestClient, cms_db: Session) -> None:
    body = client.get("/api/v1/dataset").json()

    assert body["source"] == "cms_nj"
    assert body["as_of"] == "2026-09-26"
    assert body["has_conditions"] is False
    assert "complication_rate" not in body["available_metrics"]
    assert body["metric_labels"]["cost_index"] == "Medicare spending per patient"
    assert "Medicare" in body["disclaimer"]
    assert "not a rating or endorsement" in body["disclaimer"]


def test_dataset_endpoint_describes_synthetic_data(client: TestClient, seeded_db: Session) -> None:
    body = client.get("/api/v1/dataset").json()

    assert body["source"] == "synthetic"
    assert body["as_of"] is None
    assert body["has_conditions"] is True
    assert len(body["available_metrics"]) == 6


def test_dataset_endpoint_before_any_seed_follows_the_setting(make_client: Any) -> None:
    assert make_client().get("/api/v1/dataset").json()["source"] == "synthetic"
    assert make_client(data_source="cms_nj").get("/api/v1/dataset").json()["source"] == "cms_nj"


def test_a_condition_filter_is_rejected_when_the_dataset_has_none(
    client: TestClient, cms_db: Session
) -> None:
    response = client.post(
        SEARCH_URL, json={"specialty": "cardiology", "condition": "hypertension"}
    )

    error = assert_error(response, 422, "CONDITIONS_UNAVAILABLE")
    assert "no condition data" in error["message"]
    assert error["details"] == [{"field": "condition", "message": "Not available in this dataset"}]
    assert client.get("/api/v1/conditions").json() == []


def test_parsing_never_produces_a_condition_the_dataset_lacks(
    client: TestClient, cms_db: Session
) -> None:
    response = client.post(
        "/api/v1/ai/parse-query", json={"query": "cardiologist in Testville NJ for heart failure"}
    )

    criteria = response.json()["criteria"]
    assert criteria["condition"] is None
    assert criteria["specialty"] == "cardiology"
    assert criteria["location"] == {"city": "Testville", "state": "NJ"}


def test_provider_detail_flags_missing_metrics(client: TestClient, cms_db: Session) -> None:
    body = client.get(f"/api/v1/providers/{_id(cms_db, '9000000002')}").json()

    assert body["npi"] == "9000000002"
    assert body["data_source"] == "cms"
    assert body["display_name"] == "Dr. Bob O'Tester, DO"
    assert body["quality_score"] is None
    assert body["years_experience"] == 36
    assert body["complication_rate"] is None
    assert body["accepting_new_patients"] is None
    assert body["conditions"] == []
    assert body["metric_flags"] == {
        "quality_score": "imputed",
        "years_experience": "reported",
        "complication_rate": "not_reported",
        "readmission_rate": "not_reported",
    }


def test_search_scores_missing_quality_as_the_specialty_median(
    client: TestClient, cms_db: Session
) -> None:
    items = _by_npi(_search(client, specialty="cardiology", priority="quality"))

    imputed = {c["name"]: c for c in items["9000000002"]["score"]["components"]}
    reported = {c["name"]: c for c in items["9000000001"]["score"]["components"]}
    assert imputed["quality"]["raw"] == CARDIOLOGY_QUALITY_MEDIAN
    assert imputed["quality"]["imputed"] is True
    assert imputed["experience"]["imputed"] is False
    assert reported["quality"] == {**reported["quality"], "raw": 80.5, "imputed": False}
    explanation = items["9000000002"]["explanation"]
    assert "Quality score not reported" in explanation
    assert "quality score (" not in explanation
    # CMS wording: Medicare spending per patient, relative to the specialty median.
    assert any("Medicare spending per patient" in item["explanation"] for item in items.values())
    assert not any("cost" in item["explanation"].lower() for item in items.values())


def test_missing_experience_is_imputed_too(client: TestClient, cms_db: Session) -> None:
    items = _by_npi(_search(client, specialty="primary-care"))

    for npi in ("9000000003", "9000000004"):
        experience = next(c for c in items[npi]["score"]["components"] if c["name"] == "experience")
        assert experience["imputed"] is True
        assert items[npi]["provider"]["metric_flags"]["years_experience"] == "imputed"
        assert "experience not reported" in items[npi]["explanation"].lower()


def test_detail_score_matches_the_search_for_an_imputed_provider(
    client: TestClient, cms_db: Session
) -> None:
    provider_id = _id(cms_db, "9000000011")
    searched = _by_npi(_search(client, specialty="cardiology", priority="balanced"))["9000000011"]

    detail = client.get(f"/api/v1/providers/{provider_id}", params={"priority": "balanced"}).json()

    assert detail["score"] == searched["score"]
    assert detail["explanation"] == searched["explanation"]


def test_minimum_filters_only_match_reported_values(client: TestClient, cms_db: Session) -> None:
    quality = _search(client, specialty="cardiology", min_quality_score=0)
    experience = _search(client, specialty="primary-care", min_years_experience=0)

    assert set(_by_npi(quality)) == {"9000000001", "9000000012"}
    assert experience["total"] == 0


def test_sort_by_quality_lists_imputed_scores_last(client: TestClient, cms_db: Session) -> None:
    body = _search(client, specialty="cardiology", sort="quality")

    npis = [item["provider"]["npi"] for item in body["items"]]
    assert npis[:2] == ["9000000001", "9000000012"]
    assert set(npis[2:]) == {"9000000002", "9000000011"}


def test_search_near_a_cms_city(client: TestClient, cms_db: Session) -> None:
    body = _search(
        client,
        specialty="cardiology",
        location={"city": "Testville", "state": "NJ"},
        radius_miles=25,
    )

    assert body["total"] > 0
    assert all(item["distance_miles"] <= 25 for item in body["items"])
