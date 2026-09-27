"""Load the raw files into the `staging` schema, exactly as downloaded.

Every column is text, and values are copied unchanged (an empty field stays ''). Only
column names are normalized, to lowercase snake_case, so the SQL doesn't need quoted
identifiers: "Provider Last Name" -> provider_last_name, " Org_PAC_ID" -> org_pac_id.
Each run drops and recreates the raw_* tables, so their columns follow the files.

The two national files are cut down to New Jersey while reading: MIPS to the NPIs in
the NJ extract of the NDF, ZIP centroids to New Jersey's ZIP prefixes.
"""

import csv
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from psycopg import sql
from sqlalchemy import Connection, text

from pipeline.sources import (
    COUSUB,
    MIPS,
    NDF,
    NJ_ZIP_PREFIXES,
    PHYSICIAN,
    REQUIRED_COLUMNS,
    SOURCES,
    STATE,
    ZCTA,
    Source,
)

SCHEMA = "staging"
# CSV fields can exceed the csv module's 128 KiB default in principle; none should.
csv.field_size_limit(1 << 24)


class LoadError(Exception):
    """A raw file is missing, malformed, or lacks a column the transforms need."""


@dataclass(frozen=True)
class LoadResult:
    source: str
    rows_read: int
    rows_loaded: int
    filter: str


def normalize_column(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", name.strip().lower()).strip("_")


RowFilter = Callable[[list[str]], bool]


def _column(columns: list[str], name: str, source: Source) -> int:
    try:
        return columns.index(name)
    except ValueError:
        raise LoadError(f"{source.raw_file}: no column {name!r}") from None


def _filters(raw_dir: Path) -> dict[str, tuple[str, Callable[[list[str]], RowFilter]]]:
    """source key -> (description, factory taking the normalized columns)."""

    def equals(column: str, value: str, source: Source) -> Callable[[list[str]], RowFilter]:
        def build(columns: list[str]) -> RowFilter:
            i = _column(columns, column, source)
            return lambda row: row[i] == value

        return build

    def mips_npis(columns: list[str]) -> RowFilter:
        npis = _ndf_npis(raw_dir / NDF.raw_file)
        i = _column(columns, "npi", MIPS)
        return lambda row: row[i] in npis

    def nj_zips(columns: list[str]) -> RowFilter:
        i = _column(columns, "geoid", ZCTA)
        return lambda row: row[i].startswith(NJ_ZIP_PREFIXES)

    return {
        NDF.key: (f"state = {STATE}", equals("state", STATE, NDF)),
        MIPS.key: ("npi in the NJ NDF extract", mips_npis),
        PHYSICIAN.key: (
            f"rndrng_prvdr_state_abrvtn = {STATE}",
            equals("rndrng_prvdr_state_abrvtn", STATE, PHYSICIAN),
        ),
        ZCTA.key: ("ZIP prefix 07 or 08 (New Jersey)", nj_zips),
        COUSUB.key: (f"usps = {STATE}", equals("usps", STATE, COUSUB)),
    }


def _ndf_npis(path: Path) -> set[str]:
    with path.open(newline="", encoding=NDF.encoding) as f:
        reader = csv.reader(f)
        i = _column([normalize_column(c) for c in next(reader)], "npi", NDF)
        return {row[i] for row in reader}


def _rows(source: Source, path: Path) -> tuple[list[str], Iterator[list[str]]]:
    """Normalized header plus a lazy row iterator. Checks the header up front."""
    if not path.exists():
        raise LoadError(f"{path} not found (run: python -m pipeline.extract)")
    f = path.open(newline="", encoding=source.encoding)
    reader = csv.reader(f, delimiter=source.delimiter)
    try:
        columns = [normalize_column(c) for c in next(reader)]
    except StopIteration:
        f.close()
        raise LoadError(f"{path} is empty") from None
    missing = [c for c in REQUIRED_COLUMNS[source.key] if c not in columns]
    duplicated = {c for c in columns if columns.count(c) > 1}
    if missing or duplicated:
        f.close()
        problem = f"missing columns {missing}" if missing else f"duplicate columns {duplicated}"
        raise LoadError(f"{path.name}: {problem}; the source format may have changed")

    def rows() -> Iterator[list[str]]:
        with f:
            for line, row in enumerate(reader, start=2):
                if len(row) != len(columns):
                    raise LoadError(
                        f"{path.name} line {line}: {len(row)} fields, header has {len(columns)}"
                    )
                yield row

    return columns, rows()


def load_source(connection: Connection, source: Source, raw_dir: Path) -> LoadResult:
    columns, rows = _rows(source, raw_dir / source.raw_file)
    description, make_filter = _filters(raw_dir).get(source.key, ("none", lambda _: None))
    keep = make_filter(columns)

    table = sql.Identifier(SCHEMA, source.table)
    column_list = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    cursor = connection.connection.driver_connection.cursor()
    with cursor:
        cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table))
        cursor.execute(
            sql.SQL("CREATE TABLE {} ({})").format(
                table,
                sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in columns),
            )
        )
        read = loaded = 0
        with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(table, column_list)) as copy:
            for row in rows:
                read += 1
                if keep is None or keep(row):
                    copy.write_row(row)
                    loaded += 1
    return LoadResult(source.key, read, loaded, description)


def load_all(connection: Connection, raw_dir: Path) -> list[LoadResult]:
    """Load every source and record the counts in staging.load_log."""
    _require_schema(connection)
    results = [load_source(connection, source, raw_dir) for source in SOURCES]
    connection.execute(text(f"DROP TABLE IF EXISTS {SCHEMA}.load_log"))
    connection.execute(
        text(
            f"CREATE TABLE {SCHEMA}.load_log "
            "(source text PRIMARY KEY, rows_read int, rows_loaded int, filter text)"
        )
    )
    connection.execute(
        text(f"INSERT INTO {SCHEMA}.load_log VALUES (:source, :read, :loaded, :filter)"),
        [
            {"source": r.source, "read": r.rows_read, "loaded": r.rows_loaded, "filter": r.filter}
            for r in results
        ],
    )
    return results


def _require_schema(connection: Connection) -> None:
    found = connection.scalar(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :name"),
        {"name": SCHEMA},
    )
    if not found:
        raise LoadError(f"schema {SCHEMA!r} does not exist (run: alembic upgrade head)")
