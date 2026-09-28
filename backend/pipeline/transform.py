"""Load data/raw/ into staging, run the SQL transforms, and write data/cms/.

Run from backend/ after `python -m pipeline.extract` and `alembic upgrade head`:

    python -m pipeline.transform

Writes data/cms/providers_nj.csv and data/cms/cities_nj.csv (committed, so seeding
never needs the network), adds their row counts to data/cms/MANIFEST.json, and writes
docs/data-quality.md. Everything runs in one transaction in the `staging` schema, as the
owner role (MIGRATION_DATABASE_URL, else DATABASE_URL); the app's own tables are
untouched until you seed.
"""

import argparse
import csv
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, create_engine, text

from app.core.config import get_settings
from app.services.dataset import MIN_SPENDING_PATIENTS
from pipeline import data_quality
from pipeline.extract import ExtractError, read_manifest, verify_cache, write_manifest
from pipeline.load import LoadError, load_all
from pipeline.sources import CMS_DIR, MANIFEST_PATH, RAW_DIR, STATE

SQL_DIR = Path(__file__).resolve().parent / "sql"
PROVIDERS_FILE = "providers_nj.csv"
CITIES_FILE = "cities_nj.csv"
# MIN_SPENDING_PATIENTS: spending per patient is left unreported (NULL: imputed in the app,
# never a reason to stand out) below this many patients. Defined in the app, which serves
# it in GET /dataset; the SQL reads it from staging.params.

# Output column -> formatter. None is written as an empty field.
Formatter = Callable[[Any], str]
PROVIDER_COLUMNS: dict[str, Formatter] = {
    "npi": str,
    "first_name": str,
    "last_name": str,
    "credential": str,
    "specialty": str,
    "city": str,
    "state": str,
    "zip_code": str,
    "latitude": lambda v: f"{v:.6f}",
    "longitude": lambda v: f"{v:.6f}",
    "years_experience": str,
    "quality_score": lambda v: f"{v:g}",
    "cost_index": lambda v: f"{v:.4f}",
    "patient_volume": str,
}
CITY_COLUMNS: dict[str, Formatter] = {
    "name": str,
    "state": str,
    "latitude": lambda v: f"{v:.6f}",
    "longitude": lambda v: f"{v:.6f}",
    "county_name": str,
    "population": str,
}


@dataclass(frozen=True)
class TransformResult:
    providers: int
    cities: int


def run_sql(connection: Connection, *, reference_year: int, state: str = STATE) -> None:
    """Run sql/*.sql in file-name order. Parameters reach the SQL through
    staging.params, so the files are plain SQL that can also be run by hand."""
    connection.execute(text("DROP TABLE IF EXISTS staging.params"))
    connection.execute(
        text(
            "CREATE TABLE staging.params (reference_year int NOT NULL, state text NOT NULL, "
            "min_spending_patients int NOT NULL)"
        )
    )
    connection.execute(
        text("INSERT INTO staging.params VALUES (:year, :state, :min_spending_patients)"),
        {"year": reference_year, "state": state, "min_spending_patients": MIN_SPENDING_PATIENTS},
    )
    # Straight to psycopg without parameters: it sends each file as one simple query, so
    # a file can hold several statements (and a literal % needs no escaping).
    with connection.connection.driver_connection.cursor() as cursor:
        for path in sorted(SQL_DIR.glob("*.sql")):
            cursor.execute(path.read_text(encoding="utf-8"))


def export(connection: Connection, out_dir: Path) -> TransformResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    providers = _write_csv(
        connection, "staging.cms_providers", "npi", PROVIDER_COLUMNS, out_dir / PROVIDERS_FILE
    )
    cities = _write_csv(
        connection, "staging.cms_cities", "name", CITY_COLUMNS, out_dir / CITIES_FILE
    )
    return TransformResult(providers=providers, cities=cities)


def _write_csv(
    connection: Connection,
    table: str,
    order_by: str,
    columns: dict[str, Formatter],
    path: Path,
) -> int:
    rows = connection.execute(
        text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_by}")
    ).mappings()
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(
                "" if row[name] is None else fmt(row[name]) for name, fmt in columns.items()
            )
            count += 1
    return count


def run(
    connection: Connection, *, raw_dir: Path, out_dir: Path, reference_year: int
) -> TransformResult:
    load_all(connection, raw_dir)
    run_sql(connection, reference_year=reference_year)
    return export(connection, out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform data/raw/ into data/cms/.")
    parser.add_argument(
        "--reference-year",
        type=int,
        default=date.today().year,
        help="year that years_experience is counted to (default: this year)",
    )
    args = parser.parse_args()

    try:
        verify_cache(read_manifest())
    except ExtractError as exc:
        sys.exit(f"Raw files failed verification: {exc}")

    engine = create_engine(get_settings().owner_database_url)
    try:
        with engine.begin() as connection:
            result = run(
                connection, raw_dir=RAW_DIR, out_dir=CMS_DIR, reference_year=args.reference_year
            )
            report = data_quality.collect(connection)
    except LoadError as exc:
        sys.exit(f"Load failed: {exc}")
    finally:
        engine.dispose()

    manifest = read_manifest()
    manifest["outputs"] = {
        "transformed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "reference_year": args.reference_year,
        "min_spending_patients": MIN_SPENDING_PATIENTS,
        f"data/cms/{PROVIDERS_FILE}": {"rows": result.providers},
        f"data/cms/{CITIES_FILE}": {"rows": result.cities},
    }
    write_manifest(manifest)

    markdown = data_quality.render(report, manifest)
    data_quality.DATA_QUALITY_PATH.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {CMS_DIR / PROVIDERS_FILE} ({result.providers:,} providers)")
    print(f"Wrote {CMS_DIR / CITIES_FILE} ({result.cities} cities)")
    print(f"Updated {MANIFEST_PATH} and {data_quality.DATA_QUALITY_PATH}")


if __name__ == "__main__":
    main()
