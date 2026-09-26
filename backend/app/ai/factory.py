"""Choosing the parser. The LLM client is built once at startup (it holds a connection
pool); a parser is built per request, around that request's vocabulary."""

import logging

from app.ai.base import QueryParser
from app.ai.llm_client import AnthropicClient, LLMClient
from app.ai.llm_parser import LLMQueryParser
from app.ai.rule_based_parser import RuleBasedQueryParser
from app.ai.vocabulary import Vocabulary
from app.core.config import Settings

logger = logging.getLogger(__name__)


def create_llm_client(settings: Settings) -> LLMClient | None:
    """The configured LLM client, or None to use the keyword parser only."""
    if settings.ai_provider != "anthropic":
        return None
    if settings.anthropic_api_key is None:
        logger.warning(
            "AI_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set; using the keyword parser"
        )
        return None
    return AnthropicClient(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )


def create_query_parser(llm_client: LLMClient | None, vocabulary: Vocabulary) -> QueryParser:
    keyword_parser = RuleBasedQueryParser(vocabulary)
    if llm_client is None:
        return keyword_parser
    return LLMQueryParser(llm_client, vocabulary, fallback=keyword_parser)
