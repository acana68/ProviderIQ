"""Final checks shared by both parsers, so their output is always a valid search."""

from app.ai.vocabulary import Vocabulary
from app.schemas.ai import ParsedCriteria
from app.services.ranking.weights import Priority


def finalize(criteria: ParsedCriteria, vocabulary: Vocabulary) -> tuple[ParsedCriteria, list[str]]:
    """Make criteria safe to pass straight to POST /search, and say what changed.

    - A radius or distance priority without a location would be rejected by /search, so
      they're dropped.
    - A condition that exactly one specialty treats implies that specialty.
    """
    warnings: list[str] = []
    updates: dict[str, object] = {}
    if criteria.location is None:
        if criteria.radius_miles is not None:
            updates["radius_miles"] = None
            warnings.append("Ignored the radius because no location was recognized.")
        if criteria.priority == Priority.DISTANCE:
            updates["priority"] = None
            warnings.append("Ignored the distance priority because no location was recognized.")

    condition, specialty = criteria.condition, criteria.specialty
    if condition is not None and specialty is None:
        inferred = vocabulary.infer_specialty(condition)
        if inferred is not None:
            updates["specialty"] = inferred
            warnings.append(
                f"Inferred the specialty ({vocabulary.specialties[inferred]}) from the condition."
            )
    elif condition is not None and specialty is not None:
        if specialty not in vocabulary.condition_specialties.get(condition, frozenset()):
            warnings.append(
                f"No {vocabulary.specialties[specialty]} providers treat "
                f"{vocabulary.conditions[condition]}, so the search may find nobody."
            )
    return criteria.model_copy(update=updates), warnings
