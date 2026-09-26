from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.ai import ParsedCriteria
from app.schemas.common import ParserUsed


@dataclass(frozen=True)
class ParseResult:
    criteria: ParsedCriteria
    parser_used: ParserUsed
    warnings: list[str] = field(default_factory=list)


class QueryParser(Protocol):
    """Turns a natural-language query into structured search criteria. Never runs a search
    and never raises for bad input: anything unrecognized is just left out."""

    def parse(self, query: str) -> ParseResult: ...
