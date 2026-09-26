from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ReferenceRepo
from app.core.errors import NotFoundError
from app.schemas.common import Location, error_responses
from app.schemas.reference import ConditionSummary, SpecialtySummary

router = APIRouter(tags=["reference"])


@router.get("/specialties", response_model=list[SpecialtySummary])
def list_specialties(repo: ReferenceRepo) -> list[SpecialtySummary]:
    return [
        SpecialtySummary.model_validate(row) for row in repo.list_specialties_with_provider_counts()
    ]


@router.get(
    "/conditions",
    response_model=list[ConditionSummary],
    responses=error_responses(404, 422),
)
def list_conditions(
    repo: ReferenceRepo,
    specialty: Annotated[
        str | None,
        Query(
            max_length=100,
            description="Specialty slug; only conditions treated within it are returned.",
        ),
    ] = None,
) -> list[ConditionSummary]:
    specialty_id = None
    if specialty is not None:
        found = repo.get_specialty_by_slug(specialty)
        if found is None:
            raise NotFoundError("Specialty not found")
        specialty_id = found.id
    return [ConditionSummary.model_validate(c) for c in repo.list_conditions(specialty_id)]


@router.get("/cities", response_model=list[Location])
def list_cities(repo: ReferenceRepo) -> list[Location]:
    """The locations a search can use, ordered by state then name.

    Each item has the same shape as the search body's `location`, so it can be sent back
    unchanged.
    """
    return [Location(city=city.name, state=city.state) for city in repo.list_cities()]
