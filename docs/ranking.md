# How ProviderIQ ranks providers

The ranking engine lives in `backend/app/services/ranking/`. It's pure Python: it takes
numbers in and returns scores out, with no database or web framework involved. A test
(`tests/unit/test_architecture.py`) fails if it ever imports SQLAlchemy, FastAPI, or
`app.database`, directly or indirectly.

Scoring is deterministic. The same inputs always give the same score and the same order.
A provider's score also doesn't depend on who else matched the search: every component is
normalized against fixed bounds, never against the min or max of the current results.

To see it in action without a database, run `python -m scripts.ranking_demo` from
`backend/`.

## 1. Normalize each component to [0, 1]

Higher is always better. Values past the meaningful range are clamped. Values that can only
come from a bug (negative numbers, NaN, infinity, or a radius of zero or less) raise an
error instead of being scored.

| Component | Formula | Examples | Why this curve |
|---|---|---|---|
| Quality | `quality_score / 100` | 88 → 0.88 | The score is already a rating on a fixed 0–100 scale, and a 10-point gap means the same anywhere on it. Linear, no reshaping. |
| Experience | `min(1, ln(1 + years) / ln(31))` | 0 → 0, 2 → 0.32, 5 → 0.52, 10 → 0.70, 20 → 0.89, 30+ → 1 | Diminishing returns: going from 2 to 10 years matters far more than going from 20 to 28. The `+1` keeps 0 years at exactly 0, and the cap at 30 years stops very long careers from outscoring everything else. |
| Cost | `clamp(1.5 − cost_index, 0, 1)` | 0.5 → 1, 0.9 → 0.6, 1.0 → 0.5, 1.5 → 0 | `cost_index` is 1.0 for the regional average, and real providers sit roughly between 0.5 and 1.5. That range maps linearly onto 1 → 0, so an average provider lands exactly in the middle. Anything beyond the range is clamped. |
| Volume | `volume_percentile` (clamped) | 0.7 → 0.7 | Uses the provider's percentile within their own specialty, not their raw patient count. Primary care sees thousands of patients a year and oncology hundreds, so raw counts can't be compared across specialties. |
| Distance | `clamp(1 − distance / radius, 0, 1)` | 0 → 1, 6 of 20 mi → 0.7, at the radius → 0 | A linear falloff relative to the user's own radius, so "close" is judged against this search: 5 miles is far in a 6-mile search but near in a 50-mile one. |

## 2. Weight profiles

The user's priority picks a weight profile. The profiles are defined in
`ranking/weights.py` (`PROFILES`), which is the single source of truth.

| Priority | Quality | Experience | Cost | Volume | Distance |
|---|---|---|---|---|---|
| balanced | .35 | .20 | .15 | .15 | .15 |
| quality | .55 | .20 | .05 | .10 | .10 |
| cost | .25 | .10 | .45 | .05 | .15 |
| experience | .25 | .45 | .10 | .10 | .10 |
| distance | .25 | .10 | .10 | .05 | .50 |

Every profile is validated when the module is imported, so a bad edit fails at startup.
The rules are:

- Every weight is ≥ 0.
- The weights sum to 1 (within 1e-9).
- **Quality is at least 0.25.** This is a design rule: even a cost- or distance-focused
  search must not be able to push a low-quality provider to the top just because they're
  cheap or close.

## 3. Combine the components

```
effective_weightᵢ = weightᵢ / Σ(weights of the components in use)
contributionᵢ     = 100 × effective_weightᵢ × normalizedᵢ
overall           = Σ contributionᵢ
```

The overall score is in [0, 100], and the contributions always add up exactly to it. That's
what lets the UI show "48.4 of 81.5 points" per component. The engine keeps full precision.
Rounding happens only for display, in the API schemas and in `services/explanation.py`.

### Renormalization when there's no location

If the search has no location, there's no distance to score. The distance component is
dropped, and the remaining weights are divided by their own sum so they still add up to 1.
Under the `quality` profile that sum is 0.90, so quality's effective weight becomes
0.55 / 0.90 = 0.611.

The relative importance of the remaining components stays the same. Also, an overall
score without a location isn't dragged down by a component that doesn't apply.

## 4. Sorting and tie-breaks

`priority` changes how the score is computed. `sort` only picks which column to order by.
They're kept separate on purpose.

| `sort` | Order |
|---|---|
| `match` (default) | overall score, highest first |
| `quality` | quality_score, highest first |
| `experience` | years_experience, highest first |
| `distance` | distance, nearest first; providers without a distance last |
| `cost` | cost_index, cheapest first |

Every sort then breaks ties the same way: **overall descending, then quality_score
descending, then provider id ascending.** The id makes the order total, so it never depends
on the order the database happened to return rows in. Without that, the same provider
could appear on two different pages.

## 5. Worked example

The provider has quality 88, 15 years of experience, cost index 0.9, and a volume
percentile of 0.7. They are 6 miles away in a 20-mile search, and the priority is
`quality`.

| Component | Normalized | Weight | Contribution = 100 × weight × normalized |
|---|---|---|---|
| Quality | 88 / 100 = 0.880 | .55 | 48.400 |
| Experience | ln 16 / ln 31 = 2.7726 / 3.4340 = 0.807 | .20 | 16.148 |
| Cost | 1.5 − 0.9 = 0.600 | .05 | 3.000 |
| Volume | 0.700 | .10 | 7.000 |
| Distance | 1 − 6/20 = 0.700 | .10 | 7.000 |
| **Overall** | | 1.00 | **81.548** |

The explanation is:

> Ranked mainly on quality (48.4 of 81.5 points). 15 years of experience, 6.0 miles away,
> cost 10% below average.

**The same provider with no location.** Distance is dropped. The remaining weights sum to
0.90, so each is divided by 0.90: .611, .222, .056, .111. The overall score becomes
(48.400 + 16.148 + 3.000 + 7.000) / 0.90 = **82.831**.

## Explanations

`services/explanation.py` builds a sentence from templates, using only the score breakdown
and the provider's own numbers. It never uses an LLM, so it can't claim anything the score
doesn't reflect.

- It names the component with the largest contribution.
- It states years of experience and the distance (distance is left out when there's no
  location).
- It describes cost relative to average. A `cost_index` of 1.25 reads "cost 25% above
  average", and anything that rounds to 0% reads "average cost".
