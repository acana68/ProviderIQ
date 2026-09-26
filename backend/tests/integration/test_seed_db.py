import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import City, Condition, Provider, Specialty, provider_conditions
from scripts.generate_data import REFERENCE_DIR, generate, write_csvs
from scripts.seed_db import SeedDataError, has_providers, seed

N_PROVIDERS = 50


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A data/ layout with the real reference CSVs and a small generated dataset."""
    shutil.copytree(REFERENCE_DIR, tmp_path / "reference")
    write_csvs(*generate(n_providers=N_PROVIDERS, seed=7), tmp_path / "generated")
    return tmp_path


def _line_count(path: Path) -> int:
    """Data rows in a CSV (excluding the header)."""
    return len(path.read_text(encoding="utf-8").splitlines()) - 1


def test_seed_inserts_every_row(db_session: Session, data_dir: Path) -> None:
    expected = {
        "specialties": _line_count(data_dir / "reference" / "specialties.csv"),
        "conditions": _line_count(data_dir / "reference" / "conditions.csv"),
        "cities": _line_count(data_dir / "reference" / "cities.csv"),
        "providers": N_PROVIDERS,
        "provider_conditions": _line_count(data_dir / "generated" / "provider_conditions.csv"),
    }

    counts = seed(db_session, data_dir)

    assert counts == expected
    tables = {
        "specialties": Specialty,
        "conditions": Condition,
        "cities": City,
        "providers": Provider,
        "provider_conditions": provider_conditions,
    }
    for name, table in tables.items():
        assert db_session.scalar(select(func.count()).select_from(table)) == expected[name], name


def test_seed_links_providers_to_their_conditions(db_session: Session, data_dir: Path) -> None:
    providers, links = generate(n_providers=N_PROVIDERS, seed=7)
    first = providers[0]
    expected_conditions = {
        link["condition_slug"] for link in links if link["provider_key"] == first["provider_key"]
    }

    seed(db_session, data_dir)

    provider = db_session.scalars(
        select(Provider).where(
            Provider.first_name == first["first_name"],
            Provider.last_name == first["last_name"],
            Provider.latitude == first["latitude"],
            Provider.longitude == first["longitude"],
        )
    ).one()
    assert provider.specialty.slug == first["specialty"]
    assert {condition.slug for condition in provider.conditions} == expected_conditions


def test_seed_is_repeatable(db_session: Session, data_dir: Path) -> None:
    first = seed(db_session, data_dir)
    second = seed(db_session, data_dir)

    assert second == first
    assert db_session.scalar(select(func.count()).select_from(Provider)) == N_PROVIDERS
    # RESTART IDENTITY: ids start from 1 again instead of continuing.
    assert db_session.scalar(select(func.min(Provider.id))) == 1


def test_seed_rejects_unknown_condition(db_session: Session, data_dir: Path) -> None:
    links_csv = data_dir / "generated" / "provider_conditions.csv"
    with links_csv.open("a", encoding="utf-8", newline="") as f:
        f.write("P00001,not-a-condition\n")

    with pytest.raises(SeedDataError, match="unknown condition 'not-a-condition'"):
        seed(db_session, data_dir)


def test_has_providers_tells_empty_from_seeded(db_session: Session, data_dir: Path) -> None:
    # The Docker entrypoint's `seed_db --if-empty` relies on this to never reseed.
    assert has_providers(db_session) is False

    seed(db_session, data_dir)

    assert has_providers(db_session) is True
