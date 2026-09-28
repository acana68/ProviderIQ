"""The SHA-256 check on cached raw downloads, against data/cms/MANIFEST.json."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from pipeline import extract as extract_module
from pipeline import sources
from pipeline.extract import ExtractError, extract, verify_cache, verify_download
from pipeline.sources import COUSUB, NDF

CONTENT = b"USPS|GEOID|NAME\nNJ|3400100000|Example township\n"


def _entry(content: bytes = CONTENT) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(content).hexdigest(), "downloaded_at": "2026-09-27"}


@pytest.fixture
def raw_file(tmp_path: Path) -> Path:
    path = tmp_path / COUSUB.raw_file
    path.write_bytes(CONTENT)
    return path


def test_an_unchanged_download_passes(raw_file: Path) -> None:
    verify_download(COUSUB, raw_file, _entry())


def test_a_changed_download_is_rejected(raw_file: Path) -> None:
    raw_file.write_bytes(CONTENT.replace(b"Example", b"Tampered"))

    with pytest.raises(ExtractError, match="--refresh --only cousub"):
        verify_download(COUSUB, raw_file, _entry())


def test_a_truncated_download_is_rejected(raw_file: Path) -> None:
    raw_file.write_bytes(CONTENT[:10])

    with pytest.raises(ExtractError, match="SHA-256"):
        verify_download(COUSUB, raw_file, _entry())


def test_an_entry_without_a_hash_is_rejected(raw_file: Path) -> None:
    with pytest.raises(ExtractError, match="no sha256"):
        verify_download(COUSUB, raw_file, {"downloaded_at": "2026-09-27"})


def test_verify_cache_checks_every_source(raw_file: Path) -> None:
    manifest = {"sources": {COUSUB.key: _entry()}}

    verify_cache(manifest, raw_file.parent, (COUSUB,))
    with pytest.raises(ExtractError, match="no entry"):
        verify_cache(manifest, raw_file.parent, (COUSUB, NDF))


def test_verify_cache_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ExtractError, match="not found"):
        verify_cache({"sources": {COUSUB.key: _entry()}}, tmp_path, (COUSUB,))


def test_extract_refuses_a_tampered_cached_file(
    raw_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "RAW_DIR", raw_file.parent)
    monkeypatch.setattr(
        extract_module, "read_manifest", lambda: {"sources": {COUSUB.key: _entry()}}
    )
    written: list[dict[str, Any]] = []
    monkeypatch.setattr(extract_module, "write_manifest", written.append)
    raw_file.write_bytes(CONTENT + b"NJ|3400199999|Injected row\n")

    with pytest.raises(ExtractError, match="SHA-256"):
        extract((COUSUB,), refresh=False)

    # Nothing was downloaded or recorded.
    assert written == []
