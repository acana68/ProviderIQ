from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.ai import ParsedCriteria
from app.schemas.common import ParserUsed


@dataclass(frozen=True)
class ParseResult:
    criteria: ParsedCriteria
    parser_used: ParserUsed
    warnings: list[str] = field(default_factory=list)
    # The LLM judged the query to suggest suicide or self-harm risk. The keyword check
    # (app/ai/crisis.py) is applied separately, whichever parser answered.
    crisis: bool = False


class QueryParser(Protocol):
    """Turns a natural-language query into structured search criteria. Never runs a search
    and never raises for bad input: anything unrecognized is just left out."""

    def parse(self, query: str) -> ParseResult: ...
