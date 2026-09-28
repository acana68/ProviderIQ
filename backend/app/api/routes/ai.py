import logging
import time

from fastapi import APIRouter, Depends

from app.ai.crisis import mentions_self_harm
from app.api.deps import QueryParserDep, enforce_ai_rate_limit
from app.schemas.ai import ParseQueryRequest, ParseQueryResponse
from app.schemas.common import error_responses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/parse-query",
    response_model=ParseQueryResponse,
    responses=error_responses(422, 429),
    # Listed here so it runs first: a rate-limited request never touches the database.
    dependencies=[Depends(enforce_ai_rate_limit)],
)
def parse_query(body: ParseQueryRequest, parser: QueryParserDep) -> ParseQueryResponse:
    """Natural language -> search criteria. Never runs a search: the client shows the
    criteria for editing, then sends them to POST /search."""
    start = time.perf_counter()
    result = parser.parse(body.query)
    # Either check is enough. Checked here, so it applies whichever parser answered,
    # including the keyword fallback when the LLM fails.
    crisis = result.crisis or mentions_self_harm(body.query)
    # Never the query itself, nor the crisis flag: people describe their own health here.
    logger.info(
        "parse_query",
        extra={
            "parser_used": result.parser_used,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "query_length": len(body.query),
            "warning_count": len(result.warnings),
        },
    )
    return ParseQueryResponse(
        criteria=result.criteria,
        parser_used=result.parser_used,
        warnings=result.warnings,
        crisis=crisis,
    )
