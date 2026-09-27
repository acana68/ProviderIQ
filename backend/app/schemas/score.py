from typing import Self

from pydantic import BaseModel

from app.services.ranking.engine import ComponentName, ScoreBreakdown


class ScoreComponent(BaseModel):
    name: ComponentName
    # The provider's own value: quality score, years, cost index, volume percentile, miles.
    raw: float
    # On [0, 1], higher is better.
    normalized: float
    # The weight actually applied, after renormalization.
    weight: float
    # Points toward `overall`: 100 * weight * normalized.
    contribution: float
    # True when the provider doesn't have this metric and `raw` is the specialty median
    # standing in for it (quality and experience only).
    imputed: bool


class ProviderScore(BaseModel):
    overall: float
    components: list[ScoreComponent]

    @classmethod
    def from_breakdown(cls, breakdown: ScoreBreakdown) -> Self:
        """Round the engine's full-precision values for display.

        Rounded contributions can differ from `overall` by a rounding step when summed.
        """
        return cls(
            overall=round(breakdown.overall, 1),
            components=[
                ScoreComponent(
                    name=c.name,
                    raw=round(c.raw, 3),
                    normalized=round(c.normalized, 3),
                    weight=round(c.weight, 3),
                    contribution=round(c.contribution, 1),
                    imputed=c.imputed,
                )
                for c in breakdown.components
            ],
        )
