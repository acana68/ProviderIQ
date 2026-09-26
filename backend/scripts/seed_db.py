"""Replace all provider and reference data in the database with the CSVs in data/.

Reads data/reference/*.csv and data/generated/*.csv (run scripts.generate_data first).
Deletes every row in the seeded tables, and search_logs, before inserting.

Run from backend/:  python -m scripts.seed_db
With --if-empty it does nothing when providers already exist (the Docker entrypoint uses
this, so a container restart never wipes data).
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import exists, insert, select, text
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.database.session import create_db_engine, create_session_factory
from app.models import City, Condition, Provider, Specialty, provider_conditions

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

TRUNCATE_SQL = text(
    "TRUNCATE providers, provider_conditions, cities, specialties, conditions, search_logs "
    "RESTART IDENTITY CASCADE"
)


class SeedDataError(Exception):
    """A CSV is missing, malformed, or references a row that doesn't exist."""


def seed(session: Session, data_dir: Path) -> dict[str, int]:
    """Truncate and reload everything from data_dir/reference and data_dir/generated.

    All CSVs are read and cross-checked before the database is touched, and the writes
    happen in one transaction, so a bad file never leaves the database half-seeded.
    Returns the number of rows inserted per table.
    """
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
    providers = [
        (row["provider_key"], row["specialty"], _provider_values(line, row))
        for line, row in provider_rows
    ]

    try:
        session.execute(TRUNCATE_SQL)

        specialty_ids = _insert_returning_slug_ids(
            session,
            Specialty,
            [{"slug": row["slug"], "name": row["name"]} for _, row in specialty_rows],
        )
        condition_ids = _insert_returning_slug_ids(
            session,
            Condition,
            [{"slug": row["slug"], "name": row["name"]} for _, row in condition_rows],
        )
        session.execute(
            insert(City),
            [
                {
                    "name": row["name"],
                    "state": row["state"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                }
                for _, row in city_rows
            ],
        )

        # sort_by_parameter_order: the returned ids line up with the input rows.
        provider_ids = session.scalars(
            insert(Provider).returning(Provider.id, sort_by_parameter_order=True),
            [
                values | {"specialty_id": specialty_ids[specialty]}
                for _, specialty, values in providers
            ],
        ).all()
        id_by_key = {key: id_ for (key, _, _), id_ in zip(providers, provider_ids, strict=True)}

        session.execute(
            insert(provider_conditions),
            [
                {
                    "provider_id": id_by_key[row["provider_key"]],
                    "condition_id": condition_ids[row["condition_slug"]],
                }
                for _, row in link_rows
            ],
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "specialties": len(specialty_rows),
        "conditions": len(condition_rows),
        "cities": len(city_rows),
        "providers": len(provider_rows),
        "provider_conditions": len(link_rows),
    }


def has_providers(session: Session) -> bool:
    return bool(session.scalar(select(exists().select_from(Provider))))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load data/ into the database.")
    parser.add_argument(
        "--if-empty", action="store_true", help="skip if the providers table has any rows"
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_db_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            if args.if_empty and has_providers(session):
                print("Providers already exist; skipping the seed.")
                return
            if settings.environment == "prod":
                sys.exit(
                    "Refusing to seed: ENVIRONMENT is 'prod' and seeding deletes all provider data."
                )
            print(f"Seeding {engine.url.render_as_string(hide_password=True)}")
            counts = seed(session, DATA_DIR)
    except SeedDataError as exc:
        sys.exit(f"Seed data error: {exc}")
    finally:
        engine.dispose()

    for table, count in counts.items():
        print(f"  {table:<20}{count:>6}")


def _read_csv(path: Path, columns: list[str]) -> list[tuple[int, dict[str, str]]]:
    """Rows paired with their line number in the file (the header is line 1)."""
    if not path.exists():
        hint = " (run: python -m scripts.generate_data)" if path.parent.name == "generated" else ""
        raise SeedDataError(f"{path} not found{hint}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            raise SeedDataError(f"{path} is missing columns: {', '.join(missing)}")
        rows = list(enumerate(reader, start=2))
    if not rows:
        raise SeedDataError(f"{path} has no rows")
    return rows


def _provider_values(line: int, row: dict[str, str]) -> dict[str, Any]:
    try:
        return {
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


def _parse_bool(value: str) -> bool:
    if value not in ("true", "false"):
        raise ValueError(f"expected 'true' or 'false', got {value!r}")
    return value == "true"


def _insert_returning_slug_ids(
    session: Session, model: type[Specialty] | type[Condition], rows: list[dict[str, str]]
) -> dict[str, int]:
    result = session.execute(insert(model).returning(model.slug, model.id), rows)
    return {slug: id_ for slug, id_ in result}


if __name__ == "__main__":
    main()
