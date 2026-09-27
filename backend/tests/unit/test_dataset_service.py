from datetime import date
from typing import get_args

from app.schemas.dataset import MetricName
from app.services.dataset import describe_dataset


def test_cms_dataset_description() -> None:
    info = describe_dataset(
        "cms_nj", as_of=date(2026, 9, 27), vintage="MIPS PY 2024", has_conditions=False
    )

    assert info.source == "cms_nj"
    assert info.as_of == date(2026, 9, 27)
    assert "MIPS PY 2024" in info.description
    assert info.available_metrics == [
        "quality_score",
        "years_experience",
        "cost_index",
        "patient_volume",
    ]
    assert info.metric_labels["cost_index"] == "Medicare spending per patient"
    assert set(info.metric_labels) == set(info.available_metrics)
    # CMS spending per patient isn't a price, so the description never calls it cost.
    assert "cost" not in info.description.lower()
    assert "price" not in info.description.lower()
    assert info.has_conditions is False
    # The three things the disclaimer must say about real data.
    assert "real public cms data" in info.disclaimer.lower()
    assert "Medicare fee-for-service patients only" in info.disclaimer
    assert "illustrative" in info.disclaimer
    assert "not a rating or endorsement of any clinician" in info.disclaimer


def test_synthetic_dataset_description() -> None:
    info = describe_dataset("synthetic", as_of=None, vintage=None, has_conditions=True)

    assert info.source == "synthetic"
    assert info.as_of is None
    assert info.available_metrics == list(get_args(MetricName))
    assert set(info.metric_labels) == set(info.available_metrics)
    assert info.metric_labels["cost_index"] == "Cost"
    assert info.has_conditions is True
    assert "fictional" in info.disclaimer
