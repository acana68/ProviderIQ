from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from app.models import Provider
from app.schemas.common import (
    CityName,
    Location,
    ParserUsed,
    RadiusMiles,
    Slug,
    StateCode,
)
from app.schemas.provider import ProviderSummary
from app.schemas.score import ProviderScore
from app.services.ranking.engine import (
    ComponentName,
    ProviderMetrics,
    ScoreBreakdown,
    SortOption,
)
from app.services.ranking.weights import Priority

DEFAULT_RADIUS_MILES = 25.0


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialty: Slug | None = None
    condition: Slug | None = None
    location: Location | None = None
    radius_miles: RadiusMiles = DEFAULT_RADIUS_MILES
    min_quality_score: float | None = Field(default=None, ge=0, le=100)
    min_years_experience: int | None = Field(default=None, ge=0, le=70)
    accepting_new_patients: bool | None = None
    # True: only providers with a reported quality score (none imputed; CMS data only has
    # gaps). Like min_quality_score, but without a threshold.
    require_quality_score: bool = False
    priority: Priority = Priority.BALANCED
    sort: SortOption = SortOption.MATCH
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    source: Literal["nl", "manual"] = "manual"
    # Which parser produced the criteria; only meaningful for natural-language searches.
    parser_used: ParserUsed | None = None

    @field_validator("parser_used")
    @classmethod
    def _parser_needs_nl_source(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is not None and info.data.get("source") != "nl":
            raise PydanticCustomError("nl_source_required", 'parser_used requires source="nl"')
        return value

    @field_validator("radius_miles")
    @classmethod
    def _radius_needs_location(cls, value: float, info: ValidationInfo) -> float:
        # Only runs when radius_miles was sent (the default isn't validated). A radius
        # without a location would be silently ignored, which hides a client bug.
        if "location" in info.data and info.data["location"] is None:
            raise PydanticCustomError("location_required", "radius_miles requires a location")
        return value


class ScoreContext(BaseModel):
    """Optional query params on GET /providers/{id} that ask for a score, as in a search."""

    priority: Priority | None = None
    city: CityName | None = None
    # validate_default: the check below must also run when state is missing.
    state: StateCode | None = Field(default=None, validate_default=True)
    radius_miles: RadiusMiles | None = None

    @field_validator("state")
    @classmethod
    def _city_and_state_together(cls, value: str | None, info: ValidationInfo) -> str | None:
        # A missing "city" key means the city itself was invalid; that error is enough.
        if "city" in info.data and (info.data["city"] is None) != (value is None):
            raise PydanticCustomError(
                "city_state_together", "city and state must be given together"
            )
        return value

    @field_validator("radius_miles")
    @classmethod
    def _radius_needs_location(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is not None and "city" in info.data and info.data["city"] is None:
            raise PydanticCustomError("location_required", "radius_miles requires city and state")
        return value

    @property
    def location(self) -> Location | None:
        if self.city is None or self.state is None:
            return None
        return Location(city=self.city, state=self.state)


class SearchResult(BaseModel):
    provider: ProviderSummary
    # Rounded to 0.1 mile; null when the search has no location.
    distance_miles: float | None
    score: ProviderScore
    explanation: str

    @classmethod
    def build(
        cls,
        provider: Provider,
        metrics: ProviderMetrics,
        breakdown: ScoreBreakdown,
        explanation: str,
    ) -> Self:
        return cls(
            provider=ProviderSummary.from_model(provider),
            distance_miles=_round_distance(metrics.distance_miles),
            score=ProviderScore.from_breakdown(breakdown),
            explanation=explanation,
        )


class SearchResponse(BaseModel):
    items: list[SearchResult]
    page: int
    page_size: int
    total: int
    total_pages: int
    priority: Priority
    sort: SortOption
    # Effective weights after renormalization (no distance entry without a location).
    weights_used: dict[ComponentName, float]


def _round_distance(miles: float | None) -> float | None:
    return None if miles is None else round(miles, 1)
