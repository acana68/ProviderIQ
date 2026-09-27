"""Where every raw file comes from, and the columns the SQL transforms rely on.

Dataset ids are pinned to one release (PY 2024 MIPS, CY 2024 Medicare utilization, the
2025 Census files), so a rerun downloads the same vintage. Moving to a newer release
means changing the ids here and checking REQUIRED_COLUMNS against the new files: CMS
renames fields between releases, and load.py fails loudly when one is missing.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import REPO_ROOT

STATE = "NJ"
# New Jersey's ZIP codes are 07001-08999. The ZCTA gazetteer has no state column, so
# this prefix is how its national file is cut down to New Jersey.
NJ_ZIP_PREFIXES = ("07", "08")

RAW_DIR = REPO_ROOT / "data" / "raw"
CMS_DIR = REPO_ROOT / "data" / "cms"
MANIFEST_PATH = CMS_DIR / "MANIFEST.json"

PDC_API = "https://data.cms.gov/provider-data/api/1"
DATA_CMS_API = "https://data.cms.gov/data-api/v1"
GAZETTEER = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer"
POPEST = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/totals"


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    publisher: str
    # The release this pipeline is pinned to.
    version: str
    landing_page: str
    # File name in data/raw/.
    raw_file: str
    # "," for CSV; the 2025 Census gazetteers are pipe-delimited (earlier years used tabs).
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    # A catalog id (Provider Data Catalog dataset or data.cms.gov dataset UUID), if any.
    dataset_id: str | None = None

    @property
    def raw_path(self) -> Path:
        return RAW_DIR / self.raw_file

    @property
    def table(self) -> str:
        """The staging table the raw rows are loaded into."""
        return f"raw_{self.key}"


NDF = Source(
    key="ndf",
    title="Doctors and Clinicians National Downloadable File",
    publisher="CMS Provider Data Catalog",
    # Refreshed monthly; the manifest records this release's date as "modified".
    version="Current monthly release",
    landing_page="https://data.cms.gov/provider-data/dataset/mj5m-pzi6",
    raw_file="ndf_nj.csv",
    dataset_id="mj5m-pzi6",
)
MIPS = Source(
    key="mips",
    title="PY 2024 Clinician Public Reporting: Overall MIPS Performance",
    publisher="CMS Provider Data Catalog",
    version="Performance Year 2024",
    landing_page="https://data.cms.gov/provider-data/dataset/a174-a962",
    raw_file="mips_clinician_overall_national.csv",
    dataset_id="a174-a962",
)
PHYSICIAN = Source(
    key="physician",
    title="Medicare Physician & Other Practitioners - by Provider",
    publisher="data.cms.gov",
    version="Calendar Year 2024",
    landing_page=(
        "https://data.cms.gov/provider-summary-by-type-of-service/"
        "medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider"
    ),
    raw_file="physician_by_provider_nj.csv",
    # The CY 2024 release. (The catalog also lists a "latest" alias, which moves.)
    dataset_id="4d0b2df0-1e99-4db7-a574-a571d99217f1",
)
ZCTA = Source(
    key="zcta",
    title="2025 Gazetteer: ZIP Code Tabulation Areas (national)",
    publisher="U.S. Census Bureau",
    version="2025 Gazetteer",
    landing_page="https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html",
    raw_file="2025_Gaz_zcta_national.txt",
    delimiter="|",
)
COUSUB = Source(
    key="cousub",
    title="2025 Gazetteer: County Subdivisions, New Jersey",
    publisher="U.S. Census Bureau",
    version="2025 Gazetteer",
    landing_page="https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html",
    raw_file="2025_gaz_cousubs_34.txt",
    delimiter="|",
)
POPULATION = Source(
    key="population",
    title="Subcounty Resident Population Estimates, New Jersey (Vintage 2025)",
    publisher="U.S. Census Bureau",
    version="Vintage 2025",
    landing_page="https://www.census.gov/programs-surveys/popest/data/tables.html",
    raw_file="sub-est2025_34.csv",
    # Census population files are Latin-1, not UTF-8.
    encoding="latin-1",
)

SOURCES = (NDF, MIPS, PHYSICIAN, ZCTA, COUSUB, POPULATION)

# Staging column names (normalized, see load.normalize_column) each transform reads.
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "ndf": (
        "npi",
        "ind_enrl_id",
        "provider_last_name",
        "provider_first_name",
        "cred",
        "grd_yr",
        "pri_spec",
        "org_pac_id",
        "adr_ln_1",
        "city_town",
        "state",
        "zip_code",
        "adrs_id",
    ),
    "mips": ("npi", "source", "final_mips_score"),
    "physician": (
        "rndrng_npi",
        "rndrng_prvdr_crdntls",
        "rndrng_prvdr_ent_cd",
        "rndrng_prvdr_state_abrvtn",
        "rndrng_prvdr_zip5",
        "tot_benes",
        "tot_srvcs",
        "tot_mdcr_alowd_amt",
    ),
    "zcta": ("geoid", "intptlat", "intptlong"),
    "cousub": ("usps", "geoid", "name", "intptlat", "intptlong"),
    "population": ("sumlev", "state", "county", "cousub", "name", "popestimate2025"),
}
