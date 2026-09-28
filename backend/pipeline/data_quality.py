"""Data-quality report for the CMS pipeline: what came in, what was kept, what was
dropped and why, and how complete the kept data is.

Run from backend/ after the transform:  python -m pipeline.data_quality
(python -m pipeline.transform also runs it.) Prints the report and writes
docs/data-quality.md. Reads only the staging schema.
"""

from typing import Any

from sqlalchemy import Connection, create_engine, text

from app.core.config import REPO_ROOT, get_settings
from pipeline.extract import read_manifest

DATA_QUALITY_PATH = REPO_ROOT / "docs" / "data-quality.md"

# In the order the checks run in sql/06_providers.sql.
DROP_REASONS = (
    "specialty not mapped",
    "no Medicare utilization record",
    "not an MD or DO",
    "credential not published",
    "missing name",
    "no usable Medicare volume",
    "ZIP code not located",
)
TOP_UNMAPPED = 15


def _rows(connection: Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(sql)).mappings()]


def _scalar(connection: Connection, sql: str) -> Any:
    return connection.execute(text(sql)).scalar_one()


def collect(connection: Connection) -> dict[str, Any]:
    """Every number in the report, from the staging tables the transform left behind."""
    s: dict[str, Any] = {}
    s["load_log"] = _rows(connection, "SELECT * FROM staging.load_log ORDER BY source")
    s["reference_year"] = _scalar(connection, "SELECT reference_year FROM staging.params")
    s["min_spending_patients"] = _scalar(
        connection, "SELECT min_spending_patients FROM staging.params"
    )
    s["ndf_rows"] = _scalar(connection, "SELECT count(*) FROM staging.ndf_rows")
    s["ndf_npis"] = _scalar(connection, "SELECT count(DISTINCT npi) FROM staging.ndf_rows")
    s["mapped_npis"] = _scalar(connection, "SELECT count(*) FROM staging.ndf_selected")
    s["multi_address_npis"] = _scalar(
        connection,
        """SELECT count(*) FROM (
               SELECT npi FROM staging.ndf_rows WHERE specialty IS NOT NULL
               GROUP BY npi HAVING count(DISTINCT address_id) > 1
           ) AS multi""",
    )
    s["multi_address_by_medicare_zip"] = _scalar(
        connection,
        """SELECT count(*) FROM staging.ndf_selected AS s
           WHERE s.matches_medicare_zip AND s.npi IN (
               SELECT npi FROM staging.ndf_rows WHERE specialty IS NOT NULL
               GROUP BY npi HAVING count(DISTINCT address_id) > 1
           )""",
    )
    s["drops"] = {
        row["drop_reason"]: row["n"]
        for row in _rows(
            connection,
            """SELECT drop_reason, count(*) AS n FROM staging.npi_funnel
               WHERE drop_reason IS NOT NULL GROUP BY drop_reason""",
        )
    }
    s["unmapped"] = _rows(
        connection,
        """SELECT cms_specialty, count(*) AS n FROM (
               SELECT r.npi, min(r.cms_specialty) AS cms_specialty
               FROM staging.ndf_rows AS r
               JOIN staging.npi_funnel AS f
                 ON f.npi = r.npi AND f.drop_reason = 'specialty not mapped'
               GROUP BY r.npi
           ) AS dropped
           GROUP BY cms_specialty ORDER BY n DESC, cms_specialty""",
    )
    s["matches"] = _rows(
        connection,
        """SELECT
               count(*) AS mapped,
               count(u.npi) AS in_medicare,
               count(m.final_score) AS in_mips,
               count(*) FILTER (WHERE m.zero_only) AS mips_zero_only,
               count(*) FILTER (WHERE u.npi IS NOT NULL AND m.final_score IS NOT NULL)
                   AS in_both
           FROM staging.ndf_selected AS s
           LEFT JOIN staging.medicare_utilization AS u ON u.npi = s.npi
           LEFT JOIN staging.mips_scores AS m ON m.npi = s.npi""",
    )[0]
    s["kept"] = _rows(
        connection,
        """SELECT
               count(*) AS providers,
               count(quality_score) AS with_quality,
               count(*) FILTER (WHERE mips_zero_only) AS quality_zero,
               count(years_experience) AS with_experience,
               count(*) FILTER (WHERE graduation_year IS NULL) AS no_graduation_year,
               count(*) FILTER (WHERE graduation_year IS NOT NULL AND years_experience IS NULL)
                   AS implausible_graduation_year
           FROM staging.cms_providers""",
    )[0]
    s["specialties"] = _rows(
        connection,
        """SELECT
               specialty,
               count(*) AS n,
               count(quality_score) AS with_quality,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY quality_score) AS quality_median,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY years_experience) AS years_median,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY patient_volume) AS volume_median,
               percentile_cont(0.1) WITHIN GROUP (ORDER BY cost_index) AS cost_p10,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY cost_index) AS cost_p50,
               percentile_cont(0.9) WITHIN GROUP (ORDER BY cost_index) AS cost_p90,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY spending_per_patient)
                   AS spending_median
           FROM staging.cms_providers GROUP BY specialty ORDER BY specialty""",
    )
    s["spending"] = _rows(
        connection,
        """SELECT
               c.specialty,
               count(*) AS n,
               count(*) FILTER (WHERE c.spending_status = 'reported') AS reported,
               count(*) FILTER (WHERE c.spending_status = 'suppressed') AS suppressed,
               count(*) FILTER (WHERE c.spending_status = 'too_few_patients')
                   AS too_few_patients,
               count(*) FILTER (WHERE c.spending_status = 'not_usable') AS not_usable,
               sum(u.drug_allowed_amount) / NULLIF(sum(u.allowed_amount), 0) AS drug_share
           FROM staging.cms_providers AS c
           JOIN staging.medicare_utilization AS u ON u.npi = c.npi
           GROUP BY ROLLUP (c.specialty)
           ORDER BY c.specialty NULLS LAST""",
    )
    s["cities"] = _rows(
        connection, "SELECT name, county_name, population FROM staging.cms_cities ORDER BY name"
    )
    return s


def _pct(part: int, whole: int) -> str:
    return "n/a" if whole == 0 else f"{100 * part / whole:.1f}%"


def _num(value: float | None, fmt: str = ".1f") -> str:
    return "-" if value is None else format(value, fmt)


def render(s: dict[str, Any], manifest: dict[str, Any]) -> str:
    out: list[str] = []
    add = out.append
    add("# Data quality: CMS clinicians, New Jersey\n")
    add(
        "Generated by `python -m pipeline.transform` (or `python -m pipeline.data_quality`)"
        " from the staging schema. Don't edit by hand; rerun the pipeline.\n"
    )
    outputs = manifest.get("outputs", {})
    add(
        f"Reference year for experience: {s['reference_year']}."
        + (f" Transformed {outputs['transformed_at'][:10]}." if outputs else "")
        + "\n"
    )

    add("## Sources\n")
    add("| Source | Version | Downloaded | Rows in file | Rows loaded (NJ) | Filter |")
    add("|---|---|---|---:|---:|---|")
    sources = manifest.get("sources", {})
    for row in s["load_log"]:
        meta = sources.get(row["source"], {})
        add(
            f"| {meta.get('title', row['source'])} | {meta.get('version', '')} "
            f"| {str(meta.get('downloaded_at', ''))[:10]} | {row['rows_read']:,} "
            f"| {row['rows_loaded']:,} | {row['filter']} |"
        )
    add("")

    add("## Row counts at each step\n")
    add("| Step | Rows |")
    add("|---|---:|")
    add(f"| NDF rows with a NJ practice address | {s['ndf_rows']:,} |")
    add(f"| Distinct clinicians (NPIs) in them | {s['ndf_npis']:,} |")
    remaining = s["ndf_npis"]
    for reason in DROP_REASONS:
        dropped = s["drops"].get(reason, 0)
        remaining -= dropped
        add(f"| after dropping: {reason} (-{dropped:,}) | {remaining:,} |")
    add(f"| **Providers kept** | **{s['kept']['providers']:,}** |")
    add("")
    add(
        f"One row per NPI: {s['multi_address_npis']:,} of the {s['mapped_npis']:,} mapped "
        f"clinicians list more than one NJ address. For "
        f"{s['multi_address_by_medicare_zip']:,} of them the address chosen is the one "
        "whose ZIP matches their Medicare record (rule in `sql/05_select_address.sql`).\n"
    )

    add("## Drop reasons\n")
    add("| Reason | Clinicians |")
    add("|---|---:|")
    for reason in DROP_REASONS:
        add(f"| {reason} | {s['drops'].get(reason, 0):,} |")
    add("")
    add(f"Most common unmapped primary specialties (top {TOP_UNMAPPED}):\n")
    add("| CMS primary specialty | Clinicians |")
    add("|---|---:|")
    for row in s["unmapped"][:TOP_UNMAPPED]:
        add(f"| {row['cms_specialty']} | {row['n']:,} |")
    others = s["unmapped"][TOP_UNMAPPED:]
    if others:
        add(f"| {len(others)} others | {sum(r['n'] for r in others):,} |")
    add("")

    m = s["matches"]

    def release(key: str) -> str:
        version = sources.get(key, {}).get("version")
        return f" ({version})" if version else ""

    add("## Match rates across the three CMS datasets\n")
    add("Of the clinicians with a mapped specialty (one row per NPI):\n")
    add("| Found in | Clinicians | Rate |")
    add("|---|---:|---:|")
    add(f"| NDF (mapped specialty) | {m['mapped']:,} | 100% |")
    add(
        f"| Medicare utilization{release('physician')} | {m['in_medicare']:,} "
        f"| {_pct(m['in_medicare'], m['mapped'])} |"
    )
    add(
        f"| MIPS final score above 0{release('mips')} | {m['in_mips']:,} "
        f"| {_pct(m['in_mips'], m['mapped'])} |"
    )
    add(
        "| MIPS final score of 0 only (nothing scorable submitted; treated as missing) "
        f"| {m['mips_zero_only']:,} | {_pct(m['mips_zero_only'], m['mapped'])} |"
    )
    add(
        f"| Both Medicare and a MIPS score | {m['in_both']:,} | {_pct(m['in_both'], m['mapped'])} |"
    )
    add("")

    k = s["kept"]
    located_base = k["providers"] + s["drops"].get("ZIP code not located", 0)
    add("## Completeness of the kept providers\n")
    add("| Measure | Providers | Rate |")
    add("|---|---:|---:|")
    add(
        f"| Has a MIPS score (quality) | {k['with_quality']:,} "
        f"| {_pct(k['with_quality'], k['providers'])} |"
    )
    add(
        f"| - no score because the only MIPS score is 0 | {k['quality_zero']:,} "
        f"| {_pct(k['quality_zero'], k['providers'])} |"
    )
    add(
        f"| Has years of experience | {k['with_experience']:,} "
        f"| {_pct(k['with_experience'], k['providers'])} |"
    )
    add(f"| - no graduation year published | {k['no_graduation_year']:,} | |")
    add(f"| - graduation year implausible | {k['implausible_graduation_year']:,} | |")
    add(
        f"| Located (ZIP centroid found), of those reaching that check | {k['providers']:,} "
        f"| {_pct(k['providers'], located_base)} |"
    )
    add("")
    add(
        "Missing quality, experience and spending are scored as the specialty median and "
        "flagged as imputed in the API; complication and readmission rates aren't published per "
        "clinician, so they are always null for this dataset.\n"
    )
    add(
        "**A MIPS final score of 0 counts as missing.** Source: CMS, *2024 Traditional MIPS "
        "Scoring Guide* (qpp.cms.gov). The final score is the weighted sum of the category "
        "scores. A clinician who submits no quality measure gets 0 points for quality, as "
        "does a submitted measure that misses data completeness (outside small practices). "
        "Cost needs no submission, and every scored cost measure earns 1-10 points. So a "
        "final score of exactly 0 means nothing that could be scored was submitted and no "
        "cost measure was scored: in practice, not taking part. Every such row in the CMS "
        "file has quality 0 and improvement activities 0. Scoring it as 0 would rank "
        "non-participation as the worst possible quality, so it is imputed like any other "
        "missing score (rule: `sql/03_mips_scores.sql`).\n"
    )

    minimum = s["min_spending_patients"]
    add("## Medicare spending per patient\n")
    add(
        "This dataset's `cost_index`: the Medicare allowed amount for medical (non-drug) "
        "services per beneficiary, divided by the median for the specialty among the kept "
        "NJ providers who have it (so the median is 1.0). Per patient rather than per "
        "service because Medicare pays by fee schedule: the amount per service mostly "
        "reflects which services are billed, not a price. Spending per patient measures "
        "how much care a clinician uses for each patient, though it is still influenced by "
        "how sick those patients are. Part B drugs (the file's `Drug_*` fields: codes on "
        "the ASP drug list) are left out because they mostly reflect the condition "
        "treated, such as chemotherapy, not the clinician's choices. The ranking scores "
        "spending as a percentile within the specialty (see docs/ranking.md).\n"
    )
    add(
        "Spending is **not reported** (null, scored as the specialty median and flagged, "
        "never a reason to stand out) when CMS suppressed the medical amounts, or when "
        f"fewer than {minimum} patients had medical services: over so few patients, one "
        "unusually sick or healthy patient decides the average. The suppression here is "
        "counter-suppression: the drug part covered 1-10 patients, so CMS also blanks the "
        "medical part, which would otherwise give the drug part away "
        "(rules: `sql/04_medicare_utilization.sql`, `sql/06_providers.sql`).\n"
    )
    add(
        "| Specialty | Providers | Reported | Suppressed by CMS "
        f"| Fewer than {minimum} patients | Other | Drug share of allowed amount |"
    )
    add("|---|---:|---:|---:|---:|---:|---:|")
    for row in s["spending"]:
        drug_share = None if row["drug_share"] is None else 100 * row["drug_share"]
        add(
            f"| {row['specialty'] or '**all**'} | {row['n']:,} "
            f"| {row['reported']:,} ({_pct(row['reported'], row['n'])}) "
            f"| {row['suppressed']:,} | {row['too_few_patients']:,} | {row['not_usable']:,} "
            f"| {_num(drug_share)}% |"
        )
    add("")

    add("## Per specialty\n")
    add(
        "Spending columns cover only the providers whose spending is reported. The index "
        "distribution is for reference: the ranking uses each provider's percentile within "
        "the specialty, not the index itself.\n"
    )
    add(
        "| Specialty | Providers | With MIPS | Median quality | Median years "
        "| Median Medicare patients | Spending index p10 / p50 / p90 "
        "| Median spending / patient |"
    )
    add("|---|---:|---:|---:|---:|---:|---|---:|")
    for row in s["specialties"]:
        add(
            f"| {row['specialty']} | {row['n']:,} | {_pct(row['with_quality'], row['n'])} "
            f"| {_num(row['quality_median'])} | {_num(row['years_median'], '.0f')} "
            f"| {_num(row['volume_median'], ',.0f')} "
            f"| {_num(row['cost_p10'], '.2f')} / {_num(row['cost_p50'], '.2f')} / "
            f"{_num(row['cost_p90'], '.2f')} "
            f"| ${_num(row['spending_median'], ',.2f')} |"
        )
    add("")

    add(f"## Search locations ({len(s['cities'])} NJ municipalities)\n")
    add(", ".join(row["name"] for row in s["cities"]) + ".\n")
    return "\n".join(out)


def main() -> None:
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection:
            report = collect(connection)
    finally:
        engine.dispose()
    markdown = render(report, read_manifest())
    DATA_QUALITY_PATH.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Wrote {DATA_QUALITY_PATH}")


if __name__ == "__main__":
    main()
