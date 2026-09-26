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

Suppose the provider is a cardiologist whose quality score beats 92% of other
cardiologists, and who doesn't rank that high on anything else. The explanation is then:

> Stands out for a high quality score (88/100; higher than 92% of cardiologists).
> 15 years of experience, 6.0 miles away, cost 10% below average.

**The same provider with no location.** Distance is dropped. The remaining weights sum to
0.90, so each is divided by 0.90: .611, .222, .056, .111. The overall score becomes
(48.400 + 16.148 + 3.000 + 7.000) / 0.90 = **82.831**.

## Explanations

`services/explanation.py` builds a sentence from templates, using only the score breakdown,
the provider's own numbers, and where they rank among their specialty peers. It never uses
an LLM, so it can't claim anything the data doesn't support.

### The standout: peer percentiles, not normalized scores

The lead names the factor the provider is best at **compared with the other providers in
their specialty**:

| Factor | Peer percentile (within the specialty, over all providers) |
|---|---|
| Quality | Share of peers with a lower quality score |
| Experience | Share of peers with fewer years |
| Cost | Share of peers with a *higher* cost index, so cheaper ranks higher |
| Volume | Share of peers with a lower patient volume (the same percentile the score uses) |
| Distance | No peer percentile, because distance depends on the search. Its normalized score stands in, and it only counts when it is ≥ 0.8, meaning within the nearest fifth of the radius |

The standout is the factor with the highest of these values, if that value is at least
0.80: the provider beats at least 80% of their peers on it. Otherwise the lead is "No
single standout factor." Ties go to the earlier factor (quality, experience, cost, volume,
distance).

**Why not the normalized scores?** Those curves are shaped for *ranking*, not for
comparing one factor against another. The experience curve saturates early on purpose, to
give diminishing returns:

- 13 years of experience normalizes to 0.77, while a typical quality score of 72
  normalizes to 0.72.
- So by normalized score, 13 years looks like this provider's strength, even though it's
  below average experience for most specialties.

Picking the highest normalized score made 57% of providers "stand out for experience" on
the seeded data. Peer percentiles put every factor on the same scale: "better than X% of
peers" means the same thing for quality as it does for cost. On the same data the leads
are now spread evenly:

| Lead | Providers |
|---|---|
| quality | 222 |
| cost | 216 |
| volume | 214 |
| experience | 194 |
| no single standout | 654 |

"No standout" is common by design. With four roughly independent factors, a provider has
about a 0.8⁴ ≈ 41% chance of ranking below the 80th percentile on all of them.

**These percentiles never touch the score.** The engine's input (`ProviderMetrics`) has no
field for them. Volume's percentile reaches the score as before, and is the same value
the explanation uses. The quality, experience and cost percentiles are attached only
after ranking, for the explanations of the page being returned. A test inverts them and
checks that every score and every position stays identical.

Like the volume percentile, the peer percentiles are computed over **all** providers in
the specialty, never the filtered search results. A provider is described the same way
whatever else the search asked for.

### Wording

| Standout | Lead |
|---|---|
| quality | Stands out for a high quality score (88/100; higher than 92% of cardiologists). |
| experience | Stands out for experience (25 years; more experienced than 90% of cardiologists). |
| cost | Stands out for low cost (23% below average; cheaper than 85% of cardiologists). |
| volume | Stands out for high patient volume within the specialty (busier than 80% of cardiologists). |
| distance | Stands out for being close by (2.1 miles away). |

Percentages are rounded down, so "cheaper than 85%" is never an overstatement. The peer
group is named per specialty ("cardiologists", "primary care doctors"). An unknown
specialty falls back to `<Name> providers`.

**Then the facts:** years of experience, distance (only when there's a location), and cost
relative to average. Whatever the lead already said is skipped. A `cost_index` of 1.25
reads "cost 25% above average", and anything that rounds to 0% reads "average cost".
