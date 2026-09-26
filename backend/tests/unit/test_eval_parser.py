"""The eval script's labels and scoring, without a database or API calls."""

import pytest

from app.ai.llm_parser import LLMQueryParser
from app.ai.rule_based_parser import RuleBasedQueryParser
from app.schemas.ai import ParsedCriteria
from scripts.eval_parser import CASES, FIELDS, evaluate
from tests.helpers import FakeLLMClient, reference_vocabulary


def test_there_are_about_twenty_cases() -> None:
    assert len(CASES) >= 20
    assert len({query for query, _ in CASES}) == len(CASES)


@pytest.mark.parametrize(("query", "expected"), CASES, ids=[q[:40] for q, _ in CASES])
def test_labels_only_use_real_vocabulary(query: str, expected: dict[str, object]) -> None:
    vocabulary = reference_vocabulary()
    criteria = ParsedCriteria.model_validate(expected)

    assert criteria.specialty is None or criteria.specialty in vocabulary.specialties
    assert criteria.condition is None or criteria.condition in vocabulary.conditions
    if criteria.location is not None:
        assert (criteria.location.city, criteria.location.state) in vocabulary.cities


def test_evaluate_scores_each_field() -> None:
    parser = RuleBasedQueryParser(reference_vocabulary())

    report = evaluate("rule_based", parser, CASES)

    assert report.cases == len(CASES)
    assert report.exact + len(report.misses) == len(CASES)
    assert all(0 <= report.correct_by_field[f] <= len(CASES) for f in FIELDS)
    # The phrasing the keyword parser was built for: it should get those right.
    assert report.exact >= 12


def test_llm_fallbacks_are_counted_separately() -> None:
    vocabulary = reference_vocabulary()
    parser = LLMQueryParser(
        FakeLLMClient(error=TimeoutError()), vocabulary, fallback=RuleBasedQueryParser(vocabulary)
    )

    report = evaluate("llm", parser, CASES[:3])

    assert report.fallbacks == 3
