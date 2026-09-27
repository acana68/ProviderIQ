"""The loader's checks that run before anything touches the database."""

import shutil
from pathlib import Path

import pytest

from pipeline.load import LoadError, load_source, normalize_column
from pipeline.sources import MIPS, NDF

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cms_raw"


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("NPI", "npi"),
        ("Provider Last Name", "provider_last_name"),
        (" Org_PAC_ID", "org_pac_id"),
        ("City/Town", "city_town"),
        (
            "Facility-based scoring Certification number",
            "facility_based_scoring_certification_number",
        ),
        ("final_MIPS_score", "final_mips_score"),
    ],
)
def test_normalize_column(raw: str, normalized: str) -> None:
    assert normalize_column(raw) == normalized


def test_a_renamed_source_column_fails_loudly(tmp_path: Path) -> None:
    """CMS renames fields between releases; the load must stop, not produce NULLs."""
    shutil.copytree(FIXTURE_DIR, tmp_path, dirs_exist_ok=True)
    path = tmp_path / MIPS.raw_file
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(" final_MIPS_score\n", " final_score\n", 1), encoding="utf-8")

    with pytest.raises(LoadError, match=r"missing columns \['final_mips_score'\]"):
        load_source(None, MIPS, tmp_path)  # type: ignore[arg-type]


def test_a_missing_raw_file_names_the_extract_command(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="python -m pipeline.extract"):
        load_source(None, NDF, tmp_path)  # type: ignore[arg-type]
