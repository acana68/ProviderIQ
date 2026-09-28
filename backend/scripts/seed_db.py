"""Replace all provider and reference data in the database with the CSVs in data/.

Two datasets, picked by DATA_SOURCE (or --source):

- synthetic (default): data/reference/*.csv and data/generated/*.csv (run
  scripts.generate_data first).
- cms_nj: real CMS data for New Jersey, from data/cms/ (built by backend/pipeline/;
  committed, so no network is needed). The specialties come from data/reference/, the
  search locations from data/cms/cities_nj.csv, and there are no conditions.

Deletes every row in the seeded tables, and search_logs, before inserting, and records
which dataset was loaded in dataset_metadata (GET /dataset reads it).

Run from backend/:  python -m scripts.seed_db [--source cms_nj]
With --if-empty it does nothing when providers already exist (the Docker entrypoint uses
this, so a container restart never wipes data).
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, get_args

from sqlalchemy import exists, insert, select, text
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.database.session import create_db_engine, create_session_factory
from app.models import City, Condition, DatasetMetadata, Provider, Specialty, provider_conditions
from app.schemas.dataset import DatasetSource

DATA_DIR = REPO_ROOT / "data"

PROVIDER_COLUMNS = [
    "provider_key",
    "first_name",
    "last_name",
    "credential",
    "specialty",
    "subspecialty",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "years_experience",
    "quality_score",
    "cost_index",
    "patient_volume",
    "complication_rate",
    "readmission_rate",
    "accepting_new_patients",
]
# data/cms/providers_nj.csv, as written by pipeline/transform.py.
CMS_PROVIDER_COLUMNS = [
    "npi",
    "first_name",
    "last_name",
    "credential",
    "specialty",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "years_experience",
    "quality_score",
    "cost_index",
    "patient_volume",
]
# The CMS sources whose download date and release describe the provider data.
CMS_SOURCES = ("ndf", "mips", "physician")

TRUNCATE_SQL = text(
    "TRUNCATE providers, provider_conditions, cities, specialties, conditions, search_logs, "
    "dataset_metadata RESTART IDENTITY CASCADE"
)


class SeedDataError(Exception):
    """A CSV is missing, malformed, or references a row that doesn't exist."""


@dataclass
class SeedData:
    """Everything one seed inserts, read and cross-checked before the database is touched."""

    source: DatasetSource
    specialties: list[dict[str, str]]
    cities: list[dict[str, Any]]
    # (provider_key, specialty slug, column values)
    providers: list[tuple[str, str, dict[str, Any]]]
    conditions: list[dict[str, str]] = field(default_factory=list)
    # (provider_key, condition slug)
    links: list[tuple[str, str]] = field(default_factory=list)
    as_of: date | None = None
    vintage: str | None = None


def seed(session: Session, data_dir: Path, source: DatasetSource = "synthetic") -> dict[str, int]:
    """Truncate and reload everything from data_dir for the given dataset.

    All CSVs are read and cross-checked before the database is touched, and the writes
    happen in one transaction, so a bad file never leaves the database half-seeded.
    Returns the number of rows inserted per table.
    """
    data = read_cms(data_dir) if source == "cms_nj" else read_synthetic(data_dir)

    try:
        session.execute(TRUNCATE_SQL)

        specialty_ids = _insert_returning_slug_ids(session, Specialty, data.specialties)
        condition_ids = _insert_returning_slug_ids(session, Condition, data.conditions)
        session.execute(insert(City), data.cities)

        # sort_by_parameter_order: the returned ids line up with the input rows.
        provider_ids = session.scalars(
            insert(Provider).returning(Provider.id, sort_by_parameter_order=True),
            [
                values | {"specialty_id": specialty_ids[specialty]}
                for _, specialty, values in data.providers
            ],
        ).all()
        id_by_key = {
            key: id_ for (key, _, _), id_ in zip(data.providers, provider_ids, strict=True)
        }

        if data.links:
            session.execute(
                insert(provider_conditions),
                [
                    {"provider_id": id_by_key[key], "condition_id": condition_ids[slug]}
                    for key, slug in data.links
                ],
            )
        session.add(DatasetMetadata(source=data.source, as_of=data.as_of, vintage=data.vintage))
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "specialties": len(data.specialties),
        "conditions": len(data.conditions),
        "cities": len(data.cities),
        "providers": len(data.providers),
        "provider_conditions": len(data.links),
    }


def read_synthetic(data_dir: Path) -> SeedData:
    reference_dir = data_dir / "reference"
    generated_dir = data_dir / "generated"
    specialty_rows = _read_csv(reference_dir / "specialties.csv", ["slug", "name"])
    condition_rows = _read_csv(reference_dir / "conditions.csv", ["slug", "name", "specialties"])
    city_rows = _read_csv(reference_dir / "cities.csv", ["name", "state", "latitude", "longitude"])
    provider_rows = _read_csv(generated_dir / "providers.csv", PROVIDER_COLUMNS)
    link_rows = _read_csv(
        generated_dir / "provider_conditions.csv", ["provider_key", "condition_slug"]
    )

    specialty_slugs = {row["slug"] for _, row in specialty_rows}
    condition_slugs = {row["slug"] for _, row in condition_rows}
    for line, row in condition_rows:
        for specialty in row["specialties"].split(";"):
            if specialty not in specialty_slugs:
                raise SeedDataError(
                    f"conditions.csv line {line}: condition {row['slug']!r} "
                    f"references unknown specialty {specialty!r}"
                )
    provider_keys: set[str] = set()
    for line, row in provider_rows:
        if row["specialty"] not in specialty_slugs:
            raise SeedDataError(
                f"providers.csv line {line}: unknown specialty {row['specialty']!r}"
            )
        if row["provider_key"] in provider_keys:
            raise SeedDataError(
                f"providers.csv line {line}: duplicate provider_key {row['provider_key']!r}"
            )
        provider_keys.add(row["provider_key"])
    for line, row in link_rows:
        if row["provider_key"] not in provider_keys:
            raise SeedDataError(
                f"provider_conditions.csv line {line}: unknown provider_key {row['provider_key']!r}"
            )
        if row["condition_slug"] not in condition_slugs:
            raise SeedDataError(
                f"provider_conditions.csv line {line}: unknown condition {row['condition_slug']!r}"
            )

    return SeedData(
        source="synthetic",
        specialties=[{"slug": row["slug"], "name": row["name"]} for _, row in specialty_rows],
        conditions=[{"slug": row["slug"], "name": row["name"]} for _, row in condition_rows],
        cities=[_city_values(row) for _, row in city_rows],
        providers=[
            (row["provider_key"], row["specialty"], _provider_values(line, row))
            for line, row in provider_rows
        ],
        links=[(row["provider_key"], row["condition_slug"]) for _, row in link_rows],
    )


def read_cms(data_dir: Path) -> SeedData:
    cms_dir = data_dir / "cms"
    specialty_rows = _read_csv(data_dir / "reference" / "specialties.csv", ["slug", "name"])
    city_rows = _read_csv(cms_dir / "cities_nj.csv", ["name", "state", "latitude", "longitude"])
    provider_rows = _read_csv(cms_dir / "providers_nj.csv", CMS_PROVIDER_COLUMNS)
    as_of, vintage = _cms_release(cms_dir / "MANIFEST.json")

    specialty_slugs = {row["slug"] for _, row in specialty_rows}
    npis: set[str] = set()
    for line, row in provider_rows:
        if row["specialty"] not in specialty_slugs:
            raise SeedDataError(
                f"providers_nj.csv line {line}: unknown specialty {row['specialty']!r}"
            )
        if row["npi"] in npis:
            raise SeedDataError(f"providers_nj.csv line {line}: duplicate npi {row['npi']!r}")
        npis.add(row["npi"])

    return SeedData(
        source="cms_nj",
        specialties=[{"slug": row["slug"], "name": row["name"]} for _, row in specialty_rows],
        cities=[_city_values(row) for _, row in city_rows],
        providers=[
            (row["npi"], row["specialty"], _cms_provider_values(line, row))
            for line, row in provider_rows
        ],
        as_of=as_of,
        vintage=vintage,
    )


def has_providers(session: Session) -> bool:
    return bool(session.scalar(select(exists().select_from(Provider))))


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Load data/ into the database.")
    parser.add_argument(
        "--if-empty", action="store_true", help="skip if the providers table has any rows"
    )
    parser.add_argument(
        "--source",
        choices=get_args(DatasetSource),
        default=settings.data_source,
        help=f"dataset to load (default: DATA_SOURCE, currently {settings.data_source})",
    )
    args = parser.parse_args()

    # TRUNCATE and bulk inserts: the owner role, not the app's read-mostly runtime role.
    engine = create_db_engine(settings, settings.owner_database_url)
    try:
        with create_session_factory(engine)() as session:
            if args.if_empty and has_providers(session):
                seeded = session.get(DatasetMetadata, 1)
                note = (
                    f" It holds {seeded.source} data, not {args.source}; reseed without "
                    "--if-empty to switch."
                    if seeded is not None and seeded.source != args.source
                    else ""
                )
                print(f"Providers already exist; skipping the seed.{note}")
                return
            if settings.environment == "prod":
                sys.exit(
                    "Refusing to seed: ENVIRONMENT is 'prod' and seeding deletes all provider data."
                )
            print(
                f"Seeding {args.source} data into {engine.url.render_as_string(hide_password=True)}"
            )
            counts = seed(session, DATA_DIR, args.source)
    except SeedDataError as exc:
        sys.exit(f"Seed data error: {exc}")
    finally:
        engine.dispose()

    for table, count in counts.items():
        print(f"  {table:<20}{count:>6}")


def _read_csv(path: Path, columns: list[str]) -> list[tuple[int, dict[str, str]]]:
    """Rows paired with their line number in the file (the header is line 1)."""
    if not path.exists():
        hints = {
            "generated": " (run: python -m scripts.generate_data)",
            "cms": " (run the pipeline: python -m pipeline.extract, python -m pipeline.transform)",
        }
        raise SeedDataError(f"{path} not found{hints.get(path.parent.name, '')}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            raise SeedDataError(f"{path} is missing columns: {', '.join(missing)}")
        rows = list(enumerate(reader, start=2))
    if not rows:
        raise SeedDataError(f"{path} has no rows")
    return rows


def _cms_release(manifest_path: Path) -> tuple[date, str]:
    """(as_of, vintage) from the pipeline's manifest: the earliest download date of the
    CMS files, and which release of each was used."""
    if not manifest_path.exists():
        raise SeedDataError(f"{manifest_path} not found (run: python -m pipeline.extract)")
    sources = json.loads(manifest_path.read_text(encoding="utf-8")).get("sources", {})
    missing = [key for key in CMS_SOURCES if key not in sources]
    if missing:
        raise SeedDataError(f"{manifest_path} has no entry for: {', '.join(missing)}")
    try:
        as_of = min(date.fromisoformat(sources[key]["downloaded_at"][:10]) for key in CMS_SOURCES)
    except (KeyError, ValueError) as exc:
        raise SeedDataError(f"{manifest_path}: bad downloaded_at ({exc!r})") from exc
    ndf, mips, physician = (sources[key] for key in CMS_SOURCES)
    vintage = (
        f"National Downloadable File updated {ndf.get('modified', 'unknown')}; "
        f"MIPS {mips['version']}; Medicare utilization {physician['version']}"
    )
    return as_of, vintage


def _city_values(row: dict[str, str]) -> dict[str, Any]:
    return {
        "name": row["name"],
        "state": row["state"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
    }


def _provider_values(line: int, row: dict[str, str]) -> dict[str, Any]:
    try:
        return {
            "data_source": "synthetic",
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "credential": row["credential"],
            "subspecialty": row["subspecialty"] or None,
            "city": row["city"],
            "state": row["state"],
            "zip_code": row["zip_code"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "years_experience": int(row["years_experience"]),
            "quality_score": float(row["quality_score"]),
            "cost_index": float(row["cost_index"]),
            "patient_volume": int(row["patient_volume"]),
            "complication_rate": float(row["complication_rate"]),
            "readmission_rate": float(row["readmission_rate"]),
            "accepting_new_patients": _parse_bool(row["accepting_new_patients"]),
        }
    except ValueError as exc:
        raise SeedDataError(f"providers.csv line {line}: {exc!r}") from exc


def _cms_provider_values(line: int, row: dict[str, str]) -> dict[str, Any]:
    """Empty quality, experience or cost index means not published: stored as NULL, never 0."""
    try:
        return {
            "npi": row["npi"],
            "data_source": "cms",
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "credential": row["credential"],
            "subspecialty": None,
            "city": row["city"],
            "state": row["state"],
            "zip_code": row["zip_code"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "years_experience": int(row["years_experience"]) if row["years_experience"] else None,
            "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
            # Empty: Medicare spending per patient not reported (suppressed, or too few
            # patients; see pipeline/sql/06_providers.sql).
            "cost_index": float(row["cost_index"]) if row["cost_index"] else None,
            "patient_volume": int(row["patient_volume"]),
            # Not published per clinician by CMS, and unknown.
            "complication_rate": None,
            "readmission_rate": None,
            "accepting_new_patients": None,
        }
    except ValueError as exc:
        raise SeedDataError(f"providers_nj.csv line {line}: {exc!r}") from exc


def _parse_bool(value: str) -> bool:
    if value not in ("true", "false"):
        raise ValueError(f"expected 'true' or 'false', got {value!r}")
    return value == "true"


def _insert_returning_slug_ids(
    session: Session, model: type[Specialty] | type[Condition], rows: list[dict[str, str]]
) -> dict[str, int]:
    if not rows:
        return {}
    result = session.execute(insert(model).returning(model.slug, model.id), rows)
    return {slug: id_ for slug, id_ in result}


if __name__ == "__main__":
    main()
