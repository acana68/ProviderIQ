from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import StringConstraints

from app.api.deps import ProviderRepo, ReferenceRepo
from app.core.errors import NotFoundError
from app.repositories.provider_repository import ProviderFilters
from app.schemas.common import Page, error_responses
from app.schemas.provider import ProviderDetail, ProviderSummary

router = APIRouter(prefix="/providers", tags=["providers"])

StateCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$", to_upper=True)]

# providers.id is a 32-bit integer; larger ids can't exist and would error in Postgres.
MAX_PROVIDER_ID = 2**31 - 1


@router.get(
    "",
    response_model=Page[ProviderSummary],
    responses=error_responses(404, 422),
)
def list_providers(
    provider_repo: ProviderRepo,
    reference_repo: ReferenceRepo,
    specialty: Annotated[str | None, Query(max_length=100, description="Specialty slug")] = None,
    state: Annotated[StateCode | None, Query(description="Two-letter state code, any case")] = None,
    city: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    accepting_new_patients: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ProviderSummary]:
    """Browse providers without ranking. A page past the end returns no items."""
    specialty_id = None
    if specialty is not None:
        found = reference_repo.get_specialty_by_slug(specialty)
        if found is None:
            raise NotFoundError("Specialty not found")
        specialty_id = found.id

    filters = ProviderFilters(
        specialty_id=specialty_id,
        state=state,
        city=city,
        accepting_new_patients=accepting_new_patients,
    )
    items, total = provider_repo.list_page(filters, offset=(page - 1) * page_size, limit=page_size)
    return Page.build(
        [ProviderSummary.from_model(p) for p in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{provider_id}",
    response_model=ProviderDetail,
    responses=error_responses(404, 422),
)
def get_provider(
    provider_repo: ProviderRepo,
    provider_id: Annotated[int, Path(gt=0, le=MAX_PROVIDER_ID)],
) -> ProviderDetail:
    provider = provider_repo.get(provider_id)
    if provider is None:
        raise NotFoundError("Provider not found")
    return ProviderDetail.from_model(provider)
