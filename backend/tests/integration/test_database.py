import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Provider, Specialty

EXPECTED_TABLES = {
    "specialties",
    "conditions",
    "cities",
    "providers",
    "provider_conditions",
    "search_logs",
}


def _make_provider(specialty: Specialty, **overrides: object) -> Provider:
    """A provider that satisfies every constraint, unless overridden."""
    fields: dict[str, object] = {
        "first_name": "Test",
        "last_name": "Provider",
        "credential": "MD",
        "specialty": specialty,
        "city": "Boston",
        "state": "MA",
        "zip_code": "02115",
        "latitude": 42.34,
        "longitude": -71.10,
        "years_experience": 10,
        "quality_score": 80.0,
        "cost_index": 1.0,
        "patient_volume": 1200,
        "complication_rate": 0.02,
        "readmission_rate": 0.05,
    }
    return Provider(**(fields | overrides))


def test_migrations_create_all_tables(db_engine: Engine) -> None:
    table_names = set(inspect(db_engine).get_table_names())

    assert EXPECTED_TABLES <= table_names


def test_provider_quality_score_above_100_is_rejected(db_session: Session) -> None:
    specialty = Specialty(slug="test-specialty", name="Test Specialty")
    db_session.add(_make_provider(specialty, quality_score=150))

    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    # Named by the naming convention, so we know it's this CHECK and not some other constraint.
    assert exc_info.value.orig.diag.constraint_name == "ck_providers_quality_score_range"
