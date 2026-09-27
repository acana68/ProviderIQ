from datetime import date
from typing import Literal

from pydantic import BaseModel

DatasetSource = Literal["synthetic", "cms_nj"]
MetricName = Literal[
    "quality_score",
    "years_experience",
    "cost_index",
    "patient_volume",
    "complication_rate",
    "readmission_rate",
]


class DatasetInfo(BaseModel):
    """The dataset the database holds, so the UI can label it and hide what it lacks."""

    source: DatasetSource
    label: str
    description: str
    # When the source data was retrieved; null for generated data.
    as_of: date | None
    # Provider metrics this dataset publishes. Any other metric is null for every provider.
    available_metrics: list[MetricName]
    # What each available metric means in this dataset, for display. The same field can
    # mean different things: cost_index is "Cost" for synthetic data but "Medicare
    # spending per patient" for CMS data.
    metric_labels: dict[MetricName, str]
    # False: GET /conditions is empty and a search with a condition is rejected.
    has_conditions: bool
    # Show with every page of results.
    disclaimer: str
