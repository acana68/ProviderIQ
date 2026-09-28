from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Location, ParserUsed, RadiusMiles, Slug
from app.services.ranking.weights import Priority

MAX_QUERY_LENGTH = 500


class ParsedCriteria(BaseModel):
    """Search criteria extracted from natural language. Every field matches the field of
    the same name on SearchRequest, so the frontend can pass them straight through.

    extra="forbid": a model that answers with anything else is treated as a failure.
    """

    model_config = ConfigDict(extra="forbid")

    specialty: Slug | None = Field(default=None, description="A specialty slug, or null.")
    condition: Slug | None = Field(default=None, description="A condition slug, or null.")
    location: Location | None = Field(
        default=None, description="A city and two-letter state from the allowed list, or null."
    )
    radius_miles: RadiusMiles | None = Field(
        default=None, description="Search radius in miles, only if the user gave one."
    )
    min_quality_score: float | None = Field(
        default=None, ge=0, le=100, description="Minimum quality score (0-100), or null."
    )
    min_years_experience: int | None = Field(
        default=None, ge=0, le=70, description="Minimum years of experience, or null."
    )
    accepting_new_patients: bool | None = Field(
        default=None, description="true only if the user asked for new-patient availability."
    )
    priority: Priority | None = Field(
        default=None, description="What the user cares about most, or null."
    )


class LLMParsedQuery(ParsedCriteria):
    """What the LLM answers with: the criteria, plus a flag that isn't a search filter."""

    crisis: bool | None = Field(
        default=None,
        description=(
            "true only if the text suggests the person may be thinking about suicide or "
            "self-harm, or is in danger; otherwise null. Never changes the other fields."
        ),
    )


class ParseQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_LENGTH)
    ]


class ParseQueryResponse(BaseModel):
    criteria: ParsedCriteria
    parser_used: ParserUsed
    # Human-readable notes: what was inferred, dropped, or fell back.
    warnings: list[str]
    # The query suggests suicide or self-harm risk (app/ai/crisis.py, or the LLM's flag):
    # the client shows crisis helpline information. The criteria are unaffected.
    crisis: bool = False
