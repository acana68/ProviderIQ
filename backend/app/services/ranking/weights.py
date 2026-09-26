"""Weight profiles: how much each score component counts for each search priority.

PROFILES is the single source of truth. Every profile is validated when this module is
imported, so an invalid edit fails at startup instead of silently skewing rankings.
"""

import math
from enum import StrEnum
from types import MappingProxyType
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Design rule: quality always carries at least a quarter of the score. Even a cost- or
# distance-focused search must not be able to push a low-quality provider to the top just
# because they're cheap or close.
MIN_QUALITY_WEIGHT = 0.25
SUM_TOLERANCE = 1e-9


class Priority(StrEnum):
    BALANCED = "balanced"
    QUALITY = "quality"
    COST = "cost"
    EXPERIENCE = "experience"
    DISTANCE = "distance"


class WeightProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    quality: float = Field(ge=0)
    experience: float = Field(ge=0)
    cost: float = Field(ge=0)
    volume: float = Field(ge=0)
    distance: float = Field(ge=0)

    @model_validator(mode="after")
    def _check_profile(self) -> Self:
        total = self.quality + self.experience + self.cost + self.volume + self.distance
        if not math.isclose(total, 1.0, rel_tol=0, abs_tol=SUM_TOLERANCE):
            raise ValueError(f"weights must sum to 1, got {total}")
        if self.quality < MIN_QUALITY_WEIGHT:
            raise ValueError(f"quality weight must be at least {MIN_QUALITY_WEIGHT}")
        return self


def _profile(
    quality: float, experience: float, cost: float, volume: float, distance: float
) -> WeightProfile:
    return WeightProfile(
        quality=quality, experience=experience, cost=cost, volume=volume, distance=distance
    )


# Read-only, so nothing can change a profile at runtime.
PROFILES: MappingProxyType[Priority, WeightProfile] = MappingProxyType(
    {
        #                                quality  exp   cost  volume  distance
        Priority.BALANCED: _profile(0.35, 0.20, 0.15, 0.15, 0.15),
        Priority.QUALITY: _profile(0.55, 0.20, 0.05, 0.10, 0.10),
        Priority.COST: _profile(0.25, 0.10, 0.45, 0.05, 0.15),
        Priority.EXPERIENCE: _profile(0.25, 0.45, 0.10, 0.10, 0.10),
        Priority.DISTANCE: _profile(0.25, 0.10, 0.10, 0.05, 0.50),
    }
)

if set(PROFILES) != set(Priority):
    raise RuntimeError(f"PROFILES is missing priorities: {set(Priority) - set(PROFILES)}")


def get_weights(priority: Priority | str) -> WeightProfile:
    """The profile for a priority. Raises ValueError for an unknown priority string."""
    return PROFILES[Priority(priority)]
