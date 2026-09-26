import math

import pytest
from pydantic import ValidationError

from app.services.ranking.weights import (
    MIN_QUALITY_WEIGHT,
    PROFILES,
    Priority,
    WeightProfile,
    get_weights,
)

# The documented table (docs/ranking.md). Guards against an accidental edit to PROFILES.
DOCUMENTED = {
    #                     quality exp   cost  volume distance
    Priority.BALANCED: (0.35, 0.20, 0.15, 0.15, 0.15),
    Priority.QUALITY: (0.55, 0.20, 0.05, 0.10, 0.10),
    Priority.COST: (0.25, 0.10, 0.45, 0.05, 0.15),
    Priority.EXPERIENCE: (0.25, 0.45, 0.10, 0.10, 0.10),
    Priority.DISTANCE: (0.25, 0.10, 0.10, 0.05, 0.50),
}


def _as_tuple(profile: WeightProfile) -> tuple[float, ...]:
    return (profile.quality, profile.experience, profile.cost, profile.volume, profile.distance)


def test_every_priority_has_the_documented_profile() -> None:
    assert {p: _as_tuple(profile) for p, profile in PROFILES.items()} == DOCUMENTED


@pytest.mark.parametrize("priority", list(Priority))
def test_profile_sums_to_one(priority: Priority) -> None:
    assert math.fsum(_as_tuple(PROFILES[priority])) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("priority", list(Priority))
def test_quality_weight_never_below_floor(priority: Priority) -> None:
    assert PROFILES[priority].quality >= MIN_QUALITY_WEIGHT


def test_get_weights_accepts_enum_or_string() -> None:
    assert get_weights("cost") is PROFILES[Priority.COST]
    assert get_weights(Priority.COST) is PROFILES[Priority.COST]


def test_get_weights_rejects_unknown_priority() -> None:
    with pytest.raises(ValueError):
        get_weights("cheapest")


@pytest.mark.parametrize(
    "weights",
    [
        # Sums to 0.9.
        {"quality": 0.35, "experience": 0.20, "cost": 0.15, "volume": 0.10, "distance": 0.10},
        # Sums to 1 but quality is below the floor.
        {"quality": 0.20, "experience": 0.20, "cost": 0.40, "volume": 0.10, "distance": 0.10},
        # Negative weight.
        {"quality": 0.60, "experience": -0.10, "cost": 0.30, "volume": 0.10, "distance": 0.10},
    ],
)
def test_invalid_profile_is_rejected(weights: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        WeightProfile(**weights)


def test_profiles_are_immutable() -> None:
    profile = PROFILES[Priority.BALANCED]
    with pytest.raises(ValidationError):
        profile.quality = 0.9
    with pytest.raises(TypeError):
        PROFILES[Priority.BALANCED] = PROFILES[Priority.COST]
