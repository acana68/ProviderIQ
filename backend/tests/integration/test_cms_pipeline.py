"""The whole CMS pipeline (load -> SQL transforms -> CSV export) on the fake raw files in
tests/fixtures/cms_raw/, in the test database. Its README lists what each NPI tests."""

import csv
from pathlib import Path

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from pipeline import data_quality
from pipeline.transform import CITIES_FILE, PROVIDERS_FILE, TransformResult, run
from scripts.seed_db import CMS_PROVIDER_COLUMNS

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cms_raw"
REFERENCE_YEAR = 2026

KEPT = {
    "9000000001": "cardiology",
    "9000000002": "cardiology",
    "9000000003": "primary-care",
    "9000000004": "primary-care",
    "9000000008": "dermatology",
    "9000000011": "cardiology",
    "9000000012": "cardiology",
    "9000000016": "pulmonology",
}


@pytest.fixture
def connection(db_session: Session) -> Connection:
    """The test's connection: everything the pipeline creates is rolled back after it."""
    return db_session.connection()


@pytest.fixture
def result(connection: Connection, tmp_path: Path) -> TransformResult:
    return run(connection, raw_dir=FIXTURE_DIR, out_dir=tmp_path, reference_year=REFERENCE_YEAR)


@pytest.fixture
def providers(result: TransformResult, tmp_path: Path) -> dict[str, dict[str, str]]:
    """data/cms/providers_nj.csv as written, by NPI."""
    with (tmp_path / PROVIDERS_FILE).open(newline="", encoding="utf-8") as f:
        return {row["npi"]: row for row in csv.DictReader(f)}


def _column(providers: dict[str, dict[str, str]], name: str) -> dict[str, str]:
    return {npi: row[name] for npi, row in providers.items()}


def test_national_and_other_state_rows_are_filtered_while_loading(
    connection: Connection, result: TransformResult
) -> None:
    rows = connection.execute(
        text("SELECT source, rows_read, rows_loaded FROM staging.load_log")
    ).all()

    assert {source: (read, loaded) for source, read, loaded in rows} == {
        "ndf": (22, 21),  # the NY row
        "mips": (9, 8),  # the NPI outside the NJ extract
        "physician": (13, 12),  # the NY row
        "zcta": (6, 5),  # ZIP 10001
        "cousub": (6, 6),
        "population": (9, 9),
    }


def test_raw_rows_are_loaded_as_text_exactly_as_downloaded(
    connection: Connection, result: TransformResult
) -> None:
    types = connection.execute(
        text(
            "SELECT DISTINCT data_type FROM information_schema.columns "
            "WHERE table_schema = 'staging' AND table_name LIKE 'raw\\_%'"
        )
    ).scalars()
    zips = connection.execute(
        text("SELECT zip_code FROM staging.raw_ndf WHERE npi = '9000000001' ORDER BY zip_code")
    ).scalars()
    empty_score = connection.execute(
        text("SELECT final_mips_score FROM staging.raw_mips WHERE npi = '9000000003'")
    ).scalar_one()

    assert list(types) == ["text"]
    # ZIP+4 untouched, empty fields stay '' (not NULL) in staging.
    assert list(zips) == ["07001", "070011234", "07002"]
    assert empty_score == ""


def test_output_has_the_columns_the_seed_reads(result: TransformResult, tmp_path: Path) -> None:
    with (tmp_path / PROVIDERS_FILE).open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == CMS_PROVIDER_COLUMNS
    assert result == TransformResult(providers=len(KEPT), cities=3)


def test_specialties_are_mapped_and_unmapped_ones_dropped(
    providers: dict[str, dict[str, str]],
) -> None:
    # 9000000016 is enrolled as sleep medicine (unmapped) and pulmonary disease.
    assert _column(providers, "specialty") == KEPT


def test_one_row_per_npi_by_the_documented_address_rule(
    providers: dict[str, dict[str, str]],
) -> None:
    zips = _column(providers, "zip_code")

    assert zips["9000000001"] == "07002"  # matches Medicare, beats the address listed twice
    assert zips["9000000011"] == "07001"  # located beats matching Medicare
    assert zips["9000000012"] == "07003"  # listed most often
    assert zips["9000000016"] == "07002"  # the mapped enrollment's address
    assert providers["9000000001"]["city"] == "Sampleton"


def test_coordinates_are_the_zip_centroid(providers: dict[str, dict[str, str]]) -> None:
    row = providers["9000000002"]

    assert (row["latitude"], row["longitude"]) == ("40.810000", "-74.190000")


def test_cost_index_is_spending_per_patient_over_the_specialty_median(
    providers: dict[str, dict[str, str]],
) -> None:
    # Allowed amount per beneficiary, cardiology: 10000/500 = 20, 8000/300 = 26.67,
    # 12000/200 = 60, 7500/900 = 8.33; median 23.33. (Per service it would be 100, 80,
    # 120, 150: a different order.) Primary care: 10 and 8.75; median 9.375.
    # Alone in the specialty: exactly 1.
    assert _column(providers, "cost_index") == {
        "9000000001": "0.8571",
        "9000000002": "1.1429",
        "9000000011": "2.5714",
        "9000000012": "0.3571",
        "9000000003": "1.0667",
        "9000000004": "0.9333",
        "9000000008": "1.0000",
        "9000000016": "1.0000",
    }


def test_volume_is_medicare_beneficiaries(providers: dict[str, dict[str, str]]) -> None:
    assert providers["9000000003"]["patient_volume"] == "1000"


def test_years_experience_from_graduation_year(providers: dict[str, dict[str, str]]) -> None:
    years = _column(providers, "years_experience")

    assert years["9000000001"] == "26"
    assert years["9000000002"] == "36"
    assert years["9000000012"] == "0"  # graduated in the reference year
    assert years["9000000003"] == ""  # no graduation year
    assert years["9000000004"] == ""  # 1950: implausible
    assert years["9000000016"] == ""  # in the future


def test_quality_is_the_highest_mips_score_or_null(
    providers: dict[str, dict[str, str]],
) -> None:
    assert _column(providers, "quality_score") == {
        "9000000001": "80.5",  # 0 individually, 80.5 through a group
        "9000000002": "",  # no MIPS row
        "9000000003": "",  # blank score
        "9000000004": "70",
        "9000000008": "91.25",
        "9000000011": "",  # only a 0: nothing scorable submitted, so no score
        "9000000012": "65",
        "9000000016": "88",
    }


def test_credentials_fall_back_to_the_medicare_file(
    providers: dict[str, dict[str, str]],
) -> None:
    credentials = _column(providers, "credential")

    assert credentials["9000000008"] == "MD"  # "M.D."
    assert credentials["9000000016"] == "DO"  # "D.O., PH.D."
    assert credentials["9000000002"] == "DO"


def test_names_are_title_cased(providers: dict[str, dict[str, str]]) -> None:
    row = providers["9000000002"]

    assert (row["first_name"], row["last_name"]) == ("Bob", "O'Tester")


def test_every_dropped_npi_has_one_reason(connection: Connection, result: TransformResult) -> None:
    rows = connection.execute(
        text("SELECT npi, drop_reason FROM staging.npi_funnel WHERE drop_reason IS NOT NULL")
    ).all()

    assert dict(rows) == {
        "9000000005": "specialty not mapped",
        "9000000006": "specialty not mapped",
        # Its only Medicare row is an organization's.
        "9000000007": "no Medicare utilization record",
        "9000000009": "not an MD or DO",
        "9000000014": "credential not published",
        "9000000010": "ZIP code not located",
    }


def test_cities_are_large_or_county_leading_municipalities(
    result: TransformResult, tmp_path: Path
) -> None:
    with (tmp_path / CITIES_FILE).open(newline="", encoding="utf-8") as f:
        cities = {row["name"]: row for row in csv.DictReader(f)}

    # Smallburg and Alpha County's Washington are neither 40,000+ nor their county's
    # largest; Beta County's Washington gets its county, as another Washington exists.
    assert set(cities) == {"Sampleton", "Testville", "Washington (Beta County)"}
    assert cities["Testville"]["state"] == "NJ"
    assert (cities["Testville"]["latitude"], cities["Testville"]["longitude"]) == (
        "40.600000",
        "-74.300000",
    )


def test_rerunning_gives_the_same_output(
    connection: Connection, providers: dict[str, dict[str, str]], tmp_path: Path
) -> None:
    before = (tmp_path / PROVIDERS_FILE).read_bytes()

    run(connection, raw_dir=FIXTURE_DIR, out_dir=tmp_path, reference_year=REFERENCE_YEAR)

    assert (tmp_path / PROVIDERS_FILE).read_bytes() == before


def test_data_quality_report(connection: Connection, result: TransformResult) -> None:
    report = data_quality.collect(connection)
    markdown = data_quality.render(report, {"sources": {}})

    assert report["ndf_npis"] == 14
    assert report["kept"]["providers"] == 8
    assert report["kept"]["with_quality"] == 5
    assert report["kept"]["with_experience"] == 5
    # 9000000003 has a MIPS row, but its score is blank; 9000000011's only score is 0.
    assert report["matches"] == {
        "mapped": 12,
        "in_medicare": 11,
        "in_mips": 5,
        "mips_zero_only": 1,
        "in_both": 5,
    }
    assert report["kept"]["quality_zero"] == 1
    assert report["unmapped"] == [
        {"cms_specialty": "NURSE PRACTITIONER", "n": 1},
        {"cms_specialty": "PHYSICAL THERAPIST IN PRIVATE PRACTICE", "n": 1},
    ]
    assert "| **Providers kept** | **8** |" in markdown
    assert "| specialty not mapped | 2 |" in markdown
    assert "| ZIP code not located | 1 |" in markdown
