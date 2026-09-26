"""Deterministic keyword parser: the fallback whenever the LLM isn't available.

It finds known phrases (specialties, conditions, cities, priority words) in the
normalized query, in two passes: named things first (conditions and cities), then
specialty and priority words in whatever text is left. So in "lung cancer specialist",
"lung cancer" is the condition and "cancer specialist" can't also claim the word
"cancer". Within a pass the longest phrase wins. Anything unrecognized is ignored.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from app.ai.base import ParseResult
from app.ai.criteria import finalize
from app.ai.vocabulary import Vocabulary
from app.schemas.ai import ParsedCriteria
from app.schemas.common import MAX_RADIUS_MILES, Location
from app.services.ranking.weights import Priority

Kind = Literal["specialty", "condition", "city", "priority", "accepting"]
# Matched in this order; a later pass only sees text the earlier ones left unclaimed.
_PASSES: tuple[frozenset[Kind], ...] = (
    frozenset({"condition", "city"}),
    frozenset({"specialty", "priority", "accepting"}),
)

SPECIALTY_SYNONYMS: Mapping[str, tuple[str, ...]] = {
    "cardiology": ("cardiologist", "heart doctor", "heart specialist", "cardiac"),
    "orthopedics": (
        "orthopedic",
        "orthopedist",
        "orthopaedic",
        "orthopedic surgeon",
        "bone doctor",
        "bone",
        "joint doctor",
    ),
    "dermatology": ("dermatologist", "skin doctor", "skin specialist", "skin"),
    "neurology": ("neurologist", "brain doctor", "nerve doctor"),
    "oncology": ("oncologist", "cancer doctor", "cancer specialist", "cancer"),
    "primary-care": (
        "family doctor",
        "family physician",
        "family medicine",
        "gp",
        "general practitioner",
        "primary care doctor",
        "primary care physician",
        "pcp",
        "internist",
        "internal medicine",
    ),
    "endocrinology": ("endocrinologist", "hormone doctor", "thyroid doctor"),
    "gastroenterology": ("gastroenterologist", "gi doctor", "stomach doctor", "digestive"),
    "pulmonology": ("pulmonologist", "lung doctor", "lung specialist", "respiratory"),
    "psychiatry": ("psychiatrist", "mental health", "psych"),
}

# Beyond each condition's own name (added automatically).
CONDITION_SYNONYMS: Mapping[str, tuple[str, ...]] = {
    "hypertension": ("high blood pressure",),
    "heart-failure": ("congestive heart failure", "chf"),
    "coronary-artery-disease": ("blocked arteries",),
    "atrial-fibrillation": ("afib", "a fib", "irregular heartbeat"),
    "hyperlipidemia": ("high cholesterol", "cholesterol"),
    "osteoarthritis": ("degenerative joint disease",),
    "rotator-cuff-tear": ("rotator cuff", "torn rotator cuff"),
    "acl-tear": ("acl", "torn acl"),
    "carpal-tunnel-syndrome": ("carpal tunnel",),
    "low-back-pain": ("back pain", "lower back pain"),
    "eczema": ("atopic dermatitis",),
    "migraine": ("migraines", "migraine headaches"),
    "parkinsons-disease": ("parkinsons",),
    "alzheimers-disease": ("alzheimers", "dementia"),
    "multiple-sclerosis": ("ms",),
    "colorectal-cancer": ("colon cancer",),
    "type-2-diabetes": ("type ii diabetes", "t2d", "adult onset diabetes"),
    "type-1-diabetes": ("type i diabetes", "t1d", "juvenile diabetes"),
    "hypothyroidism": ("underactive thyroid", "low thyroid"),
    "polycystic-ovary-syndrome": ("pcos",),
    "gerd": ("acid reflux", "reflux", "heartburn"),
    "irritable-bowel-syndrome": ("ibs",),
    "crohns-disease": ("crohns",),
    "ulcerative-colitis": ("colitis",),
    "copd": ("emphysema", "chronic bronchitis"),
    "sleep-apnea": ("sleep apnoea",),
    "depression": ("depressed",),
    "anxiety-disorder": ("anxiety", "panic attacks"),
    "bipolar-disorder": ("bipolar",),
    "adhd": ("attention deficit",),
    "ptsd": ("post traumatic stress",),
}

# alias -> (city, state). Used only when that city is in the vocabulary.
CITY_ALIASES: Mapping[str, tuple[str, str]] = {
    "nyc": ("New York", "NY"),
    "new york city": ("New York", "NY"),
    "manhattan": ("New York", "NY"),
    "brooklyn": ("New York", "NY"),
    "philly": ("Philadelphia", "PA"),
    "la": ("Los Angeles", "CA"),
    "sf": ("San Francisco", "CA"),
    "san fran": ("San Francisco", "CA"),
    "atl": ("Atlanta", "GA"),
}

# The bare word "near" is deliberately absent: "near New York" names a location, not a
# wish for the closest provider.
PRIORITY_PHRASES: Mapping[Priority, tuple[str, ...]] = {
    Priority.COST: (
        "cheap",
        "cheaper",
        "cheapest",
        "affordable",
        "inexpensive",
        "low cost",
        "lowest cost",
        "low price",
        "budget",
        "cost effective",
        "less expensive",
    ),
    Priority.QUALITY: (
        "best",
        "top",
        "top rated",
        "highly rated",
        "highest rated",
        "best rated",
        "high quality",
        "highest quality",
        "excellent",
    ),
    Priority.EXPERIENCE: ("experienced", "most experienced", "veteran", "seasoned"),
    Priority.DISTANCE: ("closest", "nearest", "close by", "nearby", "near me"),
}

ACCEPTING_PHRASES = (
    "accepting new patients",
    "accepts new patients",
    "taking new patients",
    "accepting patients",
    "new patients",
)

_NUMBER = r"(\d+(?:\.\d+)?)"
_RADIUS = re.compile(rf"{_NUMBER} ?(?:miles?|mi)(?![a-z])")
_YEARS = re.compile(r"(\d{1,3}) ?\+? ?(?:years?|yrs?)(?![a-z])")
_QUALITY = re.compile(
    r"(?:quality|rating|rated|score)(?: score)?(?: of)?"
    r"(?: (?:above|over|at least|minimum|min))? (\d{1,3})(?![\d.])"
)


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    kind: Kind
    value: object


class RuleBasedQueryParser:
    def __init__(self, vocabulary: Vocabulary) -> None:
        self.vocabulary = vocabulary
        self._phrases = _phrase_table(vocabulary)
        self._cities_by_name: dict[str, list[tuple[str, str]]] = {}
        for city, state in vocabulary.cities:
            self._cities_by_name.setdefault(normalize(city), []).append((city, state))

    def parse(self, query: str) -> ParseResult:
        text = normalize(query)
        matches = self._find_phrases(text)
        warnings: list[str] = []

        def first(kind: Kind, label: str) -> object | None:
            values = list(dict.fromkeys(m.value for m in matches if m.kind == kind))
            if len(values) > 1:
                warnings.append(f"Several {label} mentioned; used the first one.")
            return values[0] if values else None

        specialty = first("specialty", "specialties")
        condition = first("condition", "conditions")
        city = first("city", "cities")
        priority = first("priority", "priorities")
        criteria = ParsedCriteria(
            specialty=specialty if isinstance(specialty, str) else None,
            condition=condition if isinstance(condition, str) else None,
            location=Location(city=city[0], state=city[1]) if isinstance(city, tuple) else None,
            radius_miles=_bounded(_RADIUS, text, 1, MAX_RADIUS_MILES, "radius", warnings),
            min_quality_score=_bounded(_QUALITY, text, 0, 100, "minimum quality", warnings),
            min_years_experience=_int_or_none(
                _bounded(_YEARS, text, 0, 70, "minimum years of experience", warnings)
            ),
            accepting_new_patients=True if any(m.kind == "accepting" for m in matches) else None,
            priority=priority if isinstance(priority, Priority) else None,
        )
        criteria, final_warnings = finalize(criteria, self.vocabulary)
        warnings += final_warnings
        if criteria == ParsedCriteria():
            warnings.append("Couldn't recognize any search criteria; try the search form instead.")
        return ParseResult(criteria=criteria, parser_used="rule_based", warnings=warnings)

    def _find_phrases(self, text: str) -> list[_Match]:
        """Non-overlapping phrase matches in text order, picked pass by pass (see
        _PASSES) and longest-first within a pass."""
        candidates = [
            _Match(m.start(), m.end(), kind, value)
            for phrase, (kind, value) in self._phrases.items()
            for m in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text)
        ]
        for name, cities in self._cities_by_name.items():
            for m in re.finditer(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                city = _pick_state(cities, text[m.end() :])
                if city is not None:
                    candidates.append(_Match(m.start(), m.end(), "city", city))

        chosen: list[_Match] = []
        for kinds in _PASSES:
            in_pass = [m for m in candidates if m.kind in kinds]
            for match in sorted(in_pass, key=lambda m: (m.start - m.end, m.start)):
                if all(match.end <= c.start or match.start >= c.end for c in chosen):
                    chosen.append(match)
        return sorted(chosen, key=lambda m: m.start)


def normalize(text: str) -> str:
    """Lowercase words and numbers separated by single spaces: "Parkinson's, NYC!" ->
    "parkinsons nyc". Keeps "+" (as in "10+ years") and decimal points."""
    text = text.casefold().replace("'", "").replace("’", "")
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return " ".join(re.sub(r"[^a-z0-9.+]+", " ", text).split())


def _phrase_table(vocabulary: Vocabulary) -> dict[str, tuple[Kind, object]]:
    table: dict[str, tuple[Kind, object]] = {}

    def add(kind: Kind, value: object, phrases: Iterable[str]) -> None:
        for phrase in phrases:
            table.setdefault(normalize(phrase), (kind, value))

    for slug, name in vocabulary.specialties.items():
        add("specialty", slug, [name, slug.replace("-", " "), *SPECIALTY_SYNONYMS.get(slug, ())])
    for slug, name in vocabulary.conditions.items():
        # "Gastroesophageal Reflux Disease (GERD)" -> both the name and "gerd".
        base, _, acronym = name.partition("(")
        add(
            "condition",
            slug,
            [base, acronym.rstrip(")"), slug.replace("-", " "), *CONDITION_SYNONYMS.get(slug, ())],
        )
    for alias, (city, state) in CITY_ALIASES.items():
        if (city, state) in vocabulary.cities:
            add("city", (city, state), [alias])
    for priority, phrases in PRIORITY_PHRASES.items():
        add("priority", priority, phrases)
    add("accepting", True, ACCEPTING_PHRASES)
    table.pop("", None)
    return table


def _pick_state(cities: list[tuple[str, str]], rest: str) -> tuple[str, str] | None:
    """One city name, possibly in several states: use the state written after it
    ("portland or"), or the only one there is."""
    if len(cities) == 1:
        return cities[0]
    following = rest.split()[:1]
    return next((c for c in cities if following == [c[1].casefold()]), None)


def _bounded(
    pattern: re.Pattern[str],
    text: str,
    low: float,
    high: float,
    label: str,
    warnings: list[str],
) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = float(match.group(1))
    if not low <= value <= high:
        warnings.append(
            f"Ignored the {label} ({value:g}); it must be between {low:g} and {high:g}."
        )
        return None
    return value


def _int_or_none(value: float | None) -> int | None:
    return None if value is None else int(value)
