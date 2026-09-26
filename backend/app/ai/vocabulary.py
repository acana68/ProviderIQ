"""The closed set of values a parser may output, built from the reference data.

This package never imports repositories or the database (see docs/architecture.md): the
data arrives through the small VocabularySource protocol, which ReferenceRepository
satisfies, and deps.py wires the two together.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol


class _SlugAndName(Protocol):
    @property
    def slug(self) -> str: ...
    @property
    def name(self) -> str: ...


class _CityRow(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def state(self) -> str: ...


class _ConditionSpecialty(Protocol):
    @property
    def condition_slug(self) -> str: ...
    @property
    def specialty_slug(self) -> str: ...


class VocabularySource(Protocol):
    def list_specialties_with_provider_counts(self) -> Iterable[_SlugAndName]: ...
    def list_conditions(self) -> Iterable[_SlugAndName]: ...
    def list_condition_specialties(self) -> Iterable[_ConditionSpecialty]: ...
    def list_cities(self) -> Iterable[_CityRow]: ...


@dataclass(frozen=True)
class Vocabulary:
    # slug -> display name.
    specialties: Mapping[str, str]
    conditions: Mapping[str, str]
    # condition slug -> slugs of the specialties whose providers treat it.
    condition_specialties: Mapping[str, frozenset[str]]
    # (city, state), e.g. ("New York", "NY").
    cities: tuple[tuple[str, str], ...]

    def find_city(self, city: str, state: str) -> tuple[str, str] | None:
        """The canonical (city, state) for a case-insensitive match, or None."""
        key = (city.strip().casefold(), state.strip().upper())
        return next((c for c in self.cities if (c[0].casefold(), c[1]) == key), None)

    def infer_specialty(self, condition: str) -> str | None:
        """The one specialty that treats this condition, or None if zero or several do."""
        specialties = self.condition_specialties.get(condition, frozenset())
        return next(iter(specialties)) if len(specialties) == 1 else None


def build_vocabulary(source: VocabularySource) -> Vocabulary:
    condition_specialties: dict[str, set[str]] = defaultdict(set)
    for row in source.list_condition_specialties():
        condition_specialties[row.condition_slug].add(row.specialty_slug)
    return Vocabulary(
        specialties={s.slug: s.name for s in source.list_specialties_with_provider_counts()},
        conditions={c.slug: c.name for c in source.list_conditions()},
        condition_specialties={k: frozenset(v) for k, v in condition_specialties.items()},
        cities=tuple((c.name, c.state) for c in source.list_cities()),
    )
