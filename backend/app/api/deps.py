from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.ai.base import QueryParser
from app.ai.factory import create_query_parser
from app.ai.vocabulary import build_vocabulary
from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import retry_after_header
from app.database.session import get_db
from app.repositories.provider_repository import ProviderRepository
from app.repositories.reference_repository import ReferenceRepository
from app.repositories.search_log_repository import SearchLogRepository
from app.services.search_service import SearchService


def get_app_settings(request: Request) -> Settings:
    """The settings this app instance was built with (see create_app)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DbSession = Annotated[Session, Depends(get_db)]


def get_provider_repository(db: DbSession) -> ProviderRepository:
    return ProviderRepository(db)


def get_reference_repository(db: DbSession) -> ReferenceRepository:
    return ReferenceRepository(db)


ProviderRepo = Annotated[ProviderRepository, Depends(get_provider_repository)]
ReferenceRepo = Annotated[ReferenceRepository, Depends(get_reference_repository)]


def get_search_service(
    provider_repo: ProviderRepo, reference_repo: ReferenceRepo, db: DbSession
) -> SearchService:
    # All three repositories share the request's one session (FastAPI caches get_db).
    return SearchService(provider_repo, reference_repo, SearchLogRepository(db))


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_query_parser(request: Request, reference_repo: ReferenceRepo) -> QueryParser:
    """A parser around this request's vocabulary, using the app's shared LLM client (or
    none, for the keyword parser alone)."""
    return create_query_parser(request.app.state.llm_client, build_vocabulary(reference_repo))


QueryParserDep = Annotated[QueryParser, Depends(get_query_parser)]


def enforce_ai_rate_limit(request: Request) -> None:
    """The AI endpoint's own, stricter per-IP limit, on top of the global middleware one.

    Each parse can cost an LLM call, so this is the main cost control. Like the global
    limiter it's per process (see core/rate_limit.py).
    """
    client = request.client
    retry_after = request.app.state.ai_rate_limiter.hit(client.host if client else "unknown")
    if retry_after is not None:
        raise AppError(
            "RATE_LIMITED",
            "Too many natural-language searches; please retry later or use the search form",
            429,
            headers={"Retry-After": retry_after_header(retry_after)},
        )
