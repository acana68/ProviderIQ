from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ai.rule_based_parser import RuleBasedQueryParser, normalize
from app.schemas.ai import MAX_QUERY_LENGTH
from tests.helpers import reference_vocabulary

NY = {"city": "New York", "state": "NY"}


@pytest.fixture(scope="module")
def parser() -> RuleBasedQueryParser:
    return RuleBasedQueryParser(reference_vocabulary())


# (query, every non-null criteria field, substrings expected among the warnings)
CASES: list[tuple[str, dict[str, Any], list[str]]] = [
    (
        "Find me a highly rated cardiologist near New York with experience treating heart failure",
        {
            "specialty": "cardiology",
            "condition": "heart-failure",
            "location": NY,
            "priority": "quality",
        },
        [],
    ),
    # No specialty, and the condition is treated by two specialties: nothing inferred.
    ("someone for my high blood pressure", {"condition": "hypertension"}, []),
    # Condition treated by exactly one specialty: inferred, and said so.
    (
        "who treats heart failure?",
        {"specialty": "cardiology", "condition": "heart-failure"},
        ["Inferred the specialty (Cardiology)"],
    ),
    (
        "cheap family doctor in NYC",
        {"specialty": "primary-care", "location": NY, "priority": "cost"},
        [],
    ),
    (
        "skin doctor in philly within 10 miles",
        {
            "specialty": "dermatology",
            "location": {"city": "Philadelphia", "state": "PA"},
            "radius_miles": 10,
        },
        [],
    ),
    (
        "orthopedic surgeon for a torn ACL in Denver, 25 mi",
        {
            "specialty": "orthopedics",
            "condition": "acl-tear",
            "location": {"city": "Denver", "state": "CO"},
            "radius_miles": 25,
        },
        [],
    ),
    (
        "experienced oncologist near Chicago",
        {
            "specialty": "oncology",
            "location": {"city": "Chicago", "state": "IL"},
            "priority": "experience",
        },
        [],
    ),
    (
        "closest psychiatrist to Seattle",
        {
            "specialty": "psychiatry",
            "location": {"city": "Seattle", "state": "WA"},
            "priority": "distance",
        },
        [],
    ),
    # The bare word "near" is a location marker, not the distance priority.
    (
        "cardiologist near Houston",
        {"specialty": "cardiology", "location": {"city": "Houston", "state": "TX"}},
        [],
    ),
    (
        "affordable GP accepting new patients",
        {"specialty": "primary-care", "priority": "cost", "accepting_new_patients": True},
        [],
    ),
    (
        "best cancer doctor in LA",
        {
            "specialty": "oncology",
            "location": {"city": "Los Angeles", "state": "CA"},
            "priority": "quality",
        },
        [],
    ),
    # "lung cancer" is the condition; "cancer" doesn't also force oncology (pulmonology
    # treats it too).
    (
        "lung cancer specialist in Miami",
        {"condition": "lung-cancer", "location": {"city": "Miami", "state": "FL"}},
        [],
    ),
    (
        "My mom needs someone for her Parkinson's near Pittsburgh",
        {
            "specialty": "neurology",
            "condition": "parkinsons-disease",
            "location": {"city": "Pittsburgh", "state": "PA"},
        },
        ["Inferred the specialty (Neurology)"],
    ),
    (
        "top rated endocrinologist for type 1 diabetes",
        {"specialty": "endocrinology", "condition": "type-1-diabetes", "priority": "quality"},
        [],
    ),
    (
        "neurologist for migraines in Phoenix, AZ",
        {
            "specialty": "neurology",
            "condition": "migraine",
            "location": {"city": "Phoenix", "state": "AZ"},
        },
        [],
    ),
    (
        "mental health provider with at least 15 years of experience",
        {"specialty": "psychiatry", "min_years_experience": 15},
        [],
    ),
    (
        "dermatologist with a quality score above 80",
        {"specialty": "dermatology", "min_quality_score": 80},
        [],
    ),
    ("CARDIOLOGIST IN NEW YORK", {"specialty": "cardiology", "location": NY}, []),
    (
        "GERD specialist in San Francisco",
        {"condition": "gerd", "location": {"city": "San Francisco", "state": "CA"}},
        [],
    ),
    # Would be rejected by /search without a location, so they're dropped with a warning.
    ("nearest heart doctor", {"specialty": "cardiology"}, ["Ignored the distance priority"]),
    ("pulmonologist within 20 miles", {"specialty": "pulmonology"}, ["Ignored the radius"]),
    (
        "within 150 miles of Atlanta",
        {"location": {"city": "Atlanta", "state": "GA"}},
        ["Ignored the radius (150)"],
    ),
    (
        "skin cancer doctor",
        {"specialty": "dermatology"},
        ["Several specialties mentioned"],
    ),
    (
        "dermatologist for heart failure",
        {"specialty": "dermatology", "condition": "heart-failure"},
        ["No Dermatology providers treat Heart Failure"],
    ),
    ("asdfgh qwerty zxcvb", {}, ["Couldn't recognize any search criteria"]),
    ("", {}, ["Couldn't recognize any search criteria"]),
]


@pytest.mark.parametrize(("query", "expected", "warnings"), CASES, ids=[c[0][:40] for c in CASES])
def test_parse(
    parser: RuleBasedQueryParser, query: str, expected: dict[str, Any], warnings: list[str]
) -> None:
    result = parser.parse(query)

    assert result.parser_used == "rule_based"
    assert result.criteria.model_dump(mode="json", exclude_none=True) == expected
    for fragment in warnings:
        assert any(fragment in warning for warning in result.warnings), result.warnings
    if not warnings:
        assert result.warnings == []


def test_normalize() -> None:
    assert normalize("  Parkinson's, NYC!! 10+ yrs; 2.5 mi. ") == "parkinsons nyc 10+ yrs 2.5 mi"


@given(st.text(max_size=MAX_QUERY_LENGTH))
def test_any_text_parses_to_known_values(query: str) -> None:
    vocabulary = reference_vocabulary()
    criteria = RuleBasedQueryParser(vocabulary).parse(query).criteria

    assert criteria.specialty is None or criteria.specialty in vocabulary.specialties
    assert criteria.condition is None or criteria.condition in vocabulary.conditions
    if criteria.location is not None:
        assert (criteria.location.city, criteria.location.state) in vocabulary.cities
