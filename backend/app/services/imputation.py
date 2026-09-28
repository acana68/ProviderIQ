"""Stand-in values for metrics a provider doesn't have. Pure Python, like the engine.

Real data has gaps: most CMS clinicians have no MIPS score, some have no usable Medicare
spending per patient, and a few have no usable graduation year. The engine needs a number
for every component, so a missing value is scored as the median of the provider's
specialty and flagged as imputed.

Why not skip the component (renormalize the other weights, as with distance)? Because
that rewards missing data: a clinician with no quality score would be ranked on their
other factors alone, and so could beat an otherwise equal clinician whose real score is
merely good. The median is neutral instead. It never beats a real above-median score,
and never sinks a provider just because a number wasn't published.
"""

from dataclasses import dataclass

# If nobody in the specialty (and nobody at all) has the metric, there's no median to
# use. Zero is the conservative fallback: missing data is never rewarded.
FALLBACK = 0.0
# Where the specialty median sits among the specialty's values. A metric scored as a
# percentile (CMS spending per patient) that is imputed is scored as this.
MEDIAN_PERCENTILE = 0.5


@dataclass(frozen=True)
class ImputedValue:
    value: float
    # True when `value` is a stand-in for a missing one.
    imputed: bool


def impute(value: float | None, median: float | None) -> ImputedValue:
    """The value itself, or the median (else FALLBACK) flagged as imputed."""
    if value is not None:
        return ImputedValue(value, imputed=False)
    return ImputedValue(FALLBACK if median is None else median, imputed=True)
