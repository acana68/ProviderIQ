from typing import Self

from pydantic import BaseModel

from app.services.ranking.weights import MIN_QUALITY_WEIGHT, PROFILES, Priority, WeightProfile


class RankingWeightsResponse(BaseModel):
    """The weight profiles the ranking engine uses, straight from PROFILES."""

    # priority -> the weight of each score component; each profile sums to 1.
    profiles: dict[Priority, WeightProfile]
    # No profile gives quality less than this.
    min_quality_weight: float

    @classmethod
    def current(cls) -> Self:
        return cls(profiles=dict(PROFILES), min_quality_weight=MIN_QUALITY_WEIGHT)
