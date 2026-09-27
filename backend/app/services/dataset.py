"""What GET /dataset says about each dataset: labels, what's published, the disclaimer."""

from datetime import date

from app.schemas.dataset import DatasetInfo, DatasetSource, MetricName

SYNTHETIC_METRIC_LABELS: dict[MetricName, str] = {
    "quality_score": "Quality score",
    "years_experience": "Years of experience",
    "cost_index": "Cost",
    "patient_volume": "Patient volume",
    "complication_rate": "Complication rate",
    "readmission_rate": "Readmission rate",
}
# Only what CMS publishes per clinician: no complication or readmission rates. Each
# label says what the number actually is. In particular cost_index is Medicare spending
# per patient relative to the specialty median, not a price, so it is never called cost.
CMS_METRIC_LABELS: dict[MetricName, str] = {
    "quality_score": "MIPS final score",
    "years_experience": "Years since medical school",
    "cost_index": "Medicare spending per patient",
    "patient_volume": "Medicare patients",
}

CMS_DISCLAIMER = (
    "Real public CMS data about real clinicians, covering Medicare fee-for-service patients "
    "only. Scores are illustrative, computed by ProviderIQ from that data, and are not a "
    "rating or endorsement of any clinician by ProviderIQ or CMS."
)
SYNTHETIC_DISCLAIMER = (
    "Synthetic demo data: these providers are fictional, and scores only illustrate the "
    "ranking method."
)


def describe_dataset(
    source: DatasetSource, *, as_of: date | None, vintage: str | None, has_conditions: bool
) -> DatasetInfo:
    if source == "cms_nj":
        return DatasetInfo(
            source=source,
            label="CMS public data: New Jersey",
            description=(
                "Real New Jersey physicians in 10 specialties, from public CMS data: the "
                "Doctors and Clinicians National Downloadable File (name, specialty, "
                "practice ZIP code, graduation year), Medicare Physician & Other "
                "Practitioners (Medicare patients, and Medicare spending per patient "
                "relative to the specialty median) and MIPS final scores (quality). "
                + (f"Releases: {vintage}. " if vintage else "")
                + "Complication and readmission rates, and which conditions a clinician "
                "treats, aren't published per clinician."
            ),
            as_of=as_of,
            available_metrics=list(CMS_METRIC_LABELS),
            metric_labels=CMS_METRIC_LABELS,
            has_conditions=has_conditions,
            disclaimer=CMS_DISCLAIMER,
        )
    return DatasetInfo(
        source=source,
        label="Synthetic demo data",
        description=(
            "Fictional providers generated with a fixed random seed "
            "(scripts/generate_data.py) around 25 US cities. No real clinicians or patients."
        ),
        as_of=as_of,
        available_metrics=list(SYNTHETIC_METRIC_LABELS),
        metric_labels=SYNTHETIC_METRIC_LABELS,
        has_conditions=has_conditions,
        disclaimer=SYNTHETIC_DISCLAIMER,
    )
