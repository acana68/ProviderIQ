"""Download the raw source files into data/raw/ (gitignored) and record them in
data/cms/MANIFEST.json.

Run from backend/:  python -m pipeline.extract [--refresh] [--only ndf,mips,...]

Files already in data/raw/ are kept (the cache); --refresh downloads them again. Where
the source API can filter by state, only New Jersey is requested; the national files
(MIPS, ZIP centroids) are saved whole and cut down to New Jersey while loading.
Standard library only, like scripts/smoke_test.py.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.sources import (
    COUSUB,
    DATA_CMS_API,
    GAZETTEER,
    MANIFEST_PATH,
    MIPS,
    NDF,
    PDC_API,
    PHYSICIAN,
    POPEST,
    POPULATION,
    SOURCES,
    STATE,
    ZCTA,
    Source,
)

USER_AGENT = "ProviderIQ-pipeline/1.0 (public data extract)"
TIMEOUT_SECONDS = 300
RETRIES = 3
# data.cms.gov data-api pages: 5000 rows is the largest page it serves.
PAGE_SIZE = 5000
CHUNK_BYTES = 1 << 20


class ExtractError(Exception):
    pass


def _open(url: str) -> Any:
    """urlopen with retries and backoff; the caller closes the response."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, RETRIES + 1):
        try:
            return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        except OSError as exc:
            if attempt == RETRIES:
                raise ExtractError(f"GET {url} failed after {RETRIES} attempts: {exc}") from exc
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def _get_json(url: str) -> Any:
    with _open(url) as response:
        return json.load(response)


def _stream_to(url: str, path: Path) -> None:
    """Download to a .part file, then rename, so an interrupted download never looks cached."""
    part = path.with_suffix(path.suffix + ".part")
    with _open(url) as response, part.open("wb") as out:
        while chunk := response.read(CHUNK_BYTES):
            out.write(chunk)
    part.replace(path)


def _pdc_metadata(dataset_id: str) -> dict[str, Any]:
    return _get_json(f"{PDC_API}/metastore/schemas/dataset/items/{dataset_id}")


def extract_ndf(path: Path) -> dict[str, Any]:
    """The NDF filtered to State = NJ on the server, as CSV with the file's own headers."""
    assert NDF.dataset_id is not None
    query = urllib.parse.urlencode(
        {
            "format": "csv",
            "conditions[0][property]": "state",
            "conditions[0][value]": STATE,
            "conditions[0][operator]": "=",
        }
    )
    url = f"{PDC_API}/datastore/query/{NDF.dataset_id}/0/download?{query}"
    _stream_to(url, path)
    meta = _pdc_metadata(NDF.dataset_id)
    return {"url": url, "filter": f"state = {STATE} (server side)", "modified": meta["modified"]}


def extract_mips(path: Path) -> dict[str, Any]:
    """The whole national file: it has no state column, so it is filtered by NPI when
    loading (to the NPIs in the NJ extract of the NDF)."""
    assert MIPS.dataset_id is not None
    meta = _pdc_metadata(MIPS.dataset_id)
    # The file URL has a content hash in it, so it's looked up rather than pinned.
    url = meta["distribution"][0]["downloadURL"]
    _stream_to(url, path)
    return {
        "url": url,
        "filter": "none (national file; filtered to NJ NDF NPIs while loading)",
        "modified": meta["modified"],
    }


def _physician_pages(base: str, filter_query: str, expected: int) -> Iterator[dict[str, str]]:
    offset = 0
    while offset < expected:
        page = _get_json(f"{base}?{filter_query}&size={PAGE_SIZE}&offset={offset}")
        if not page:
            break
        yield from page
        offset += len(page)


def extract_physician(path: Path) -> dict[str, Any]:
    """The data.cms.gov API filtered to NJ rendering providers, paged, written as CSV with
    the API's field names (they're the same as the CSV download's headers)."""
    base = f"{DATA_CMS_API}/dataset/{PHYSICIAN.dataset_id}/data"
    filter_query = urllib.parse.urlencode({"filter[Rndrng_Prvdr_State_Abrvtn]": STATE})
    expected = int(_get_json(f"{base}/stats?{filter_query}")["found_rows"])

    part = path.with_suffix(path.suffix + ".part")
    written = 0
    with part.open("w", newline="", encoding="utf-8") as out:
        writer: csv.DictWriter[str] | None = None
        for row in _physician_pages(base, filter_query, expected):
            if writer is None:
                writer = csv.DictWriter(out, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
            written += 1
    if written != expected:
        part.unlink()
        raise ExtractError(f"physician: API reported {expected} NJ rows but served {written}")
    part.replace(path)
    return {
        "url": f"{base}?{filter_query}",
        "filter": f"Rndrng_Prvdr_State_Abrvtn = {STATE} (server side)",
    }


def extract_zcta(path: Path) -> dict[str, Any]:
    """National ZCTA centroids. Published as a zip; the one text file inside is kept."""
    url = f"{GAZETTEER}/2025_Gaz_zcta_national.zip"
    with _open(url) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    part = path.with_suffix(path.suffix + ".part")
    with archive.open(ZCTA.raw_file) as member, part.open("wb") as out:
        while chunk := member.read(CHUNK_BYTES):
            out.write(chunk)
    part.replace(path)
    return {"url": url, "filter": "none (national file; ZIP prefixes 07/08 kept while loading)"}


def extract_cousub(path: Path) -> dict[str, Any]:
    url = f"{GAZETTEER}/{COUSUB.raw_file}"
    _stream_to(url, path)
    return {"url": url, "filter": "state file (New Jersey only)"}


def extract_population(path: Path) -> dict[str, Any]:
    url = f"{POPEST}/{POPULATION.raw_file}"
    _stream_to(url, path)
    return {"url": url, "filter": "state file (New Jersey only)"}


EXTRACTORS: dict[str, Callable[[Path], dict[str, Any]]] = {
    NDF.key: extract_ndf,
    MIPS.key: extract_mips,
    PHYSICIAN.key: extract_physician,
    ZCTA.key: extract_zcta,
    COUSUB.key: extract_cousub,
    POPULATION.key: extract_population,
}


def count_rows(source: Source, path: Path) -> int:
    """Data rows (the header excluded), parsed as CSV so quoted newlines count once."""
    with path.open(newline="", encoding=source.encoding) as f:
        return sum(1 for _ in csv.reader(f, delimiter=source.delimiter)) - 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _describe(source: Source) -> dict[str, Any]:
    """The manifest fields that come from sources.py rather than from the download."""
    return {
        "title": source.title,
        "publisher": source.publisher,
        "dataset_id": source.dataset_id,
        "version": source.version,
        "landing_page": source.landing_page,
    }


def read_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"state": STATE, "sources": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def extract(sources: tuple[Source, ...], *, refresh: bool) -> dict[str, Any]:
    manifest = read_manifest()
    for source in sources:
        path = source.raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = manifest["sources"].get(source.key)
        if path.exists() and not refresh and entry is not None:
            # Keep the download's details, but describe the source as sources.py now does.
            entry.update(_describe(source))
            print(f"  {source.key:<11} cached      {path.name}")
            continue
        if path.exists() and not refresh:
            # A file with no manifest entry (e.g. copied in by hand): record it as found.
            details: dict[str, Any] = {"url": None, "filter": "unknown (file was already here)"}
            downloaded_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        else:
            print(f"  {source.key:<11} downloading ...", flush=True)
            details = EXTRACTORS[source.key](path)
            downloaded_at = datetime.now(UTC)
        manifest["sources"][source.key] = {
            **_describe(source),
            **details,
            "raw_file": f"data/raw/{source.raw_file}",
            "downloaded_at": downloaded_at.isoformat(timespec="seconds"),
            "rows": count_rows(source, path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        print(f"  {source.key:<11} {manifest['sources'][source.key]['rows']:>9,} rows  {path.name}")
    write_manifest(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download raw CMS and Census files.")
    parser.add_argument("--refresh", action="store_true", help="download again even if cached")
    parser.add_argument(
        "--only", help="comma-separated source keys: " + ",".join(s.key for s in SOURCES)
    )
    args = parser.parse_args()

    sources = SOURCES
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {s.key for s in SOURCES}
        if unknown:
            sys.exit(f"Unknown source(s): {', '.join(sorted(unknown))}")
        sources = tuple(s for s in SOURCES if s.key in wanted)
    try:
        extract(sources, refresh=args.refresh)
    except ExtractError as exc:
        sys.exit(f"Extract failed: {exc}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
