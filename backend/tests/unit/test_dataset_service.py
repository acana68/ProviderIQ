import json
from datetime import date
from typing import get_args

from app.core.config import REPO_ROOT
from app.schemas.dataset import MetricName
from app.services.dataset import MIN_SPENDING_PATIENTS, describe_dataset
from app.services.explanation import PEER_NOUNS


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
    assert set(info.metric_short_labels) == set(info.available_metrics)
    assert info.metric_short_labels["cost_index"] == "Spending"
    assert info.min_spending_patients == MIN_SPENDING_PATIENTS == 30
    assert info.peer_nouns == PEER_NOUNS
    assert info.peer_nouns["primary-care"] == "primary care doctors"
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
    assert set(info.metric_short_labels) == set(info.available_metrics)
    assert info.min_spending_patients is None
    assert info.peer_nouns == PEER_NOUNS
    assert info.has_conditions is True
    assert "fictional" in info.disclaimer


def test_short_labels_are_short() -> None:
    for source in ("synthetic", "cms_nj"):
        info = describe_dataset(source, as_of=None, vintage=None, has_conditions=True)
        for metric, short in info.metric_short_labels.items():
            assert len(short) <= 17, (source, metric, short)
            assert len(short) <= len(info.metric_labels[metric])


def test_the_committed_cms_data_used_the_served_spending_minimum() -> None:
    """GET /dataset serves MIN_SPENDING_PATIENTS; the committed data/cms/ must have been
    built with it. If this fails, rerun python -m pipeline.transform."""
    manifest = json.loads((REPO_ROOT / "data" / "cms" / "MANIFEST.json").read_text("utf-8"))

    assert manifest["outputs"]["min_spending_patients"] == MIN_SPENDING_PATIENTS
