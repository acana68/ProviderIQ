import copy
import logging
from typing import Any

from app.ai.base import ParseResult, QueryParser
from app.ai.criteria import finalize
from app.ai.llm_client import LLMClient
from app.ai.prompts import build_system_prompt, build_user_message
from app.ai.vocabulary import Vocabulary
from app.schemas.ai import ParsedCriteria
from app.schemas.common import Location

logger = logging.getLogger(__name__)

FALLBACK_WARNING = "AI parser unavailable; used keyword matching instead."


class LLMQueryParser:
    """Parses with the LLM, and never trusts it.

    The output must validate against ParsedCriteria (closed schema, extra fields rejected),
    then every slug and city is checked against the vocabulary. Any failure along the way
    (timeout, API error, malformed or extra output) returns the rule-based result instead,
    so parsing never fails outright.
    """

    def __init__(self, client: LLMClient, vocabulary: Vocabulary, fallback: QueryParser) -> None:
        self.client = client
        self.vocabulary = vocabulary
        self.fallback = fallback
        self._system_prompt = build_system_prompt(vocabulary)
        self._schema = criteria_json_schema()

    def parse(self, query: str) -> ParseResult:
        try:
            raw = self.client.complete_json(
                self._system_prompt, build_user_message(query), self._schema
            )
            criteria = ParsedCriteria.model_validate(raw)
        # Any failure at all falls back. Only the exception type is logged: messages can
        # quote the model's output or the request, and so the user's query.
        except Exception as exc:
            logger.warning(
                "AI parser failed; used the keyword parser",
                extra={"error_type": type(exc).__name__},
            )
            result = self.fallback.parse(query)
            return ParseResult(
                criteria=result.criteria,
                parser_used="rule_based",
                warnings=[FALLBACK_WARNING, *result.warnings],
            )

        criteria, warnings = self._drop_unknown_values(criteria)
        criteria, final_warnings = finalize(criteria, self.vocabulary)
        return ParseResult(criteria=criteria, parser_used="llm", warnings=warnings + final_warnings)

    def _drop_unknown_values(self, criteria: ParsedCriteria) -> tuple[ParsedCriteria, list[str]]:
        """Schema-valid isn't enough: a slug or city must also exist. Warnings don't repeat
        the rejected value, since it could be anything the model (or the query) produced."""
        warnings: list[str] = []
        updates: dict[str, object] = {}
        if criteria.specialty is not None:
            slug = criteria.specialty.strip().lower()
            updates["specialty"] = slug if slug in self.vocabulary.specialties else None
            if updates["specialty"] is None:
                warnings.append("Ignored a specialty the AI suggested that isn't in the directory.")
        if criteria.condition is not None:
            slug = criteria.condition.strip().lower()
            updates["condition"] = slug if slug in self.vocabulary.conditions else None
            if updates["condition"] is None:
                warnings.append("Ignored a condition the AI suggested that isn't in the directory.")
        if criteria.location is not None:
            city = self.vocabulary.find_city(criteria.location.city, criteria.location.state)
            updates["location"] = None if city is None else Location(city=city[0], state=city[1])
            if city is None:
                warnings.append("Ignored a location the AI suggested that isn't in the city list.")
        return criteria.model_copy(update=updates), warnings


def criteria_json_schema() -> dict[str, Any]:
    """ParsedCriteria's JSON schema with $refs inlined, so it's one self-contained object."""
    schema = ParsedCriteria.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = copy.deepcopy(definitions[node["$ref"].rsplit("/", 1)[-1]])
                return inline(target | {k: v for k, v in node.items() if k != "$ref"})
            return {key: inline(value) for key, value in node.items()}
        if isinstance(node, list):
            return [inline(item) for item in node]
        return node

    return inline(schema)
