# ProviderIQ API

All endpoints are under `/api/v1`. Responses are JSON. Interactive docs (OpenAPI) are at
http://localhost:8000/docs when the backend is running. They're served by the backend
directly, and the nginx front end on port 8080 proxies only `/api/`.

The examples below come from the default seeded dataset (1,500 providers, seed 42), but
they're trimmed for length.

## Conventions

### Errors

Every error has the same shape:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Specialty not found",
    "request_id": "6ef2292b-7e31-4880-99ee-ce983f43fef5"
  }
}
```

Errors about specific request fields also include `details`, one entry per field. The
submitted value is never echoed back.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "request_id": "e3c4f669-c9a4-4eed-bd3e-069ab5859127",
    "details": [
      { "field": "page_size", "message": "Input should be less than or equal to 100" }
    ]
  }
}
```

| Code | Status | When |
|---|---|---|
| `BAD_REQUEST` | 400 | Malformed request, e.g. an invalid `Content-Length` header |
| `NOT_FOUND` | 404 | Unknown route, provider id, or specialty slug |
| `METHOD_NOT_ALLOWED` | 405 | Wrong HTTP method for the route (see the `Allow` header) |
| `PAYLOAD_TOO_LARGE` | 413 | Request body over `MAX_REQUEST_BODY_BYTES` (default 64 KiB) |
| `VALIDATION_ERROR` | 422 | Malformed request: invalid parameter or body field, unknown body field |
| `INVALID_SEARCH` | 422 | Well-formed criteria that can't be used: an unknown specialty or condition slug, or `priority`/`sort` of `distance` without a location |
| `LOCATION_NOT_FOUND` | 422 | City/state not in `GET /cities` |
| `CONDITIONS_UNAVAILABLE` | 422 | A `condition` on a search when the dataset has no condition data (CMS; see `GET /dataset`) |
| `RATE_LIMITED` | 429 | Over `RATE_LIMIT_PER_MINUTE` (default 120), or `AI_RATE_LIMIT_PER_MINUTE` (default 10) on `/ai/parse-query`. Wait `Retry-After` seconds |
| `INTERNAL_ERROR` | 500 | Unexpected server error. Details go to the server log only |

### Request IDs

Every response has an `X-Request-ID` header, and error bodies repeat it as `request_id`.
Clients can send their own `X-Request-ID` (up to 64 characters of `A-Z a-z 0-9 - _`).
Any other value is replaced with a generated UUID. Server log lines for the request
include the same ID.

### Rate limiting

Requests are limited per client IP over a sliding one-minute window. `/health` is exempt.
The limit is counted per server process.

### CORS

Only origins listed in `CORS_ORIGINS` are allowed (default `http://localhost:5173`).
Allowed methods are `GET` and `POST`. Allowed request headers are `Content-Type` and
`X-Request-ID`. `X-Request-ID` is exposed to browser code. Credentials (cookies) are not
supported.

### Pagination

List endpoints that paginate return:

```json
{ "items": [], "page": 1, "page_size": 20, "total": 22, "total_pages": 2 }
```

A `page` past the end returns `200` with empty `items`.

---

## `GET /health`

App and database status. Returns `503` with `"status": "degraded"` when the database is
unreachable. Not rate limited.

```json
{
  "status": "ok",
  "app": "ProviderIQ",
  "version": "0.1.0",
  "environment": "dev",
  "database": "ok"
}
```

## `GET /specialties`

All specialties, ordered by name, each with the number of providers in it.

```json
[
  { "id": 1, "slug": "cardiology", "name": "Cardiology", "provider_count": 162 },
  { "id": 3, "slug": "dermatology", "name": "Dermatology", "provider_count": 134 }
]
```

## `GET /conditions`

Conditions, ordered by name.

| Param | Type | Notes |
|---|---|---|
| `specialty` | slug, optional | Only conditions treated by at least one provider in this specialty. Unknown slug → `404` |

`GET /conditions?specialty=cardiology`:

```json
[
  { "id": 4, "slug": "atrial-fibrillation", "name": "Atrial Fibrillation" },
  { "id": 3, "slug": "coronary-artery-disease", "name": "Coronary Artery Disease" }
]
```

## `GET /cities`

The locations a search can use, ordered by state, then name. Each item has exactly the
shape of the search body's `location`, so it can be sent back unchanged. Location lookups
match the city name case-insensitively.

```json
[
  { "city": "Phoenix", "state": "AZ" },
  { "city": "Los Angeles", "state": "CA" },
  { "city": "San Diego", "state": "CA" }
]
```

## `GET /dataset`

Which dataset the database holds, so the UI can label it, show its disclaimer, and hide
what it doesn't have. Read from what the seed script recorded, so it always describes the
data actually loaded; only an unseeded database falls back to the `DATA_SOURCE` setting.

```json
{
  "source": "cms_nj",
  "label": "CMS public data: New Jersey",
  "description": "Real New Jersey physicians in 10 specialties, from public CMS data: … Releases: National Downloadable File updated 2026-08-18; MIPS Performance Year 2024; Medicare utilization Calendar Year 2024. …",
  "as_of": "2026-09-27",
  "available_metrics": ["quality_score", "years_experience", "cost_index", "patient_volume"],
  "metric_labels": {
    "quality_score": "MIPS final score",
    "years_experience": "Years since medical school",
    "cost_index": "Medicare spending per patient",
    "patient_volume": "Medicare patients"
  },
  "has_conditions": false,
  "disclaimer": "Real public CMS data about real clinicians, covering Medicare fee-for-service patients only. Scores are illustrative, computed by ProviderIQ from that data, and are not a rating or endorsement of any clinician by ProviderIQ or CMS."
}
```

`source` is `synthetic` or `cms_nj`. `as_of` is when the CMS files were downloaded (the
earliest of the three), `null` for synthetic data. Metrics missing from
`available_metrics` are `null` for every provider. `metric_labels` names each available
metric as the dataset means it; the same field can differ between datasets (`cost_index`
is "Cost" for synthetic data). With `has_conditions: false`,
`GET /conditions` is empty and a search with a `condition` is rejected.

## `GET /providers`

Browse providers without ranking. Results are ordered by last name, first name, then id,
so paging is stable.

| Param | Type | Notes |
|---|---|---|
| `specialty` | slug, optional | Unknown slug → `404` |
| `state` | 2 letters, optional | Case-insensitive (`ny` = `NY`) |
| `city` | string, optional | Exact match, case-insensitive |
| `accepting_new_patients` | bool, optional | `true` / `false` |
| `page` | int ≥ 1 | Default `1` |
| `page_size` | int 1–100 | Default `20` |

`GET /providers?specialty=cardiology&state=ny&page_size=2`:

```json
{
  "items": [
    {
      "id": 444,
      "npi": null,
      "data_source": "synthetic",
      "display_name": "Dr. Eric Alexander, MD",
      "specialty": { "slug": "cardiology", "name": "Cardiology" },
      "subspecialty": null,
      "city": "New York",
      "state": "NY",
      "years_experience": 18,
      "quality_score": 73.7,
      "cost_index": 0.89,
      "accepting_new_patients": true,
      "metric_flags": { "quality_score": "reported", "years_experience": "reported", "complication_rate": "reported", "readmission_rate": "reported" }
    },
    {
      "id": 1332,
      "npi": null,
      "data_source": "synthetic",
      "display_name": "Dr. Holly Blair, MD",
      "specialty": { "slug": "cardiology", "name": "Cardiology" },
      "subspecialty": "Heart Failure",
      "city": "New York",
      "state": "NY",
      "years_experience": 3,
      "quality_score": 68.5,
      "cost_index": 0.88,
      "accepting_new_patients": true,
      "metric_flags": { "quality_score": "reported", "years_experience": "reported", "complication_rate": "reported", "readmission_rate": "reported" }
    }
  ],
  "page": 1,
  "page_size": 2,
  "total": 22,
  "total_pages": 11
}
```

`cost_index` is relative to the regional average: `1.0` is average and lower is cheaper.
In the CMS dataset it means something else: **Medicare spending per patient** (allowed
amount per beneficiary), where `1.0` is the median for the provider's specialty in New
Jersey. Label it with `GET /dataset`'s `metric_labels`, not as cost.

`npi` is the provider's National Provider Identifier (CMS data only; `null` for synthetic
providers), and `data_source` is `synthetic` or `cms`.

### Missing metrics

Real data has gaps, so `years_experience`, `quality_score`, `complication_rate`,
`readmission_rate` and `accepting_new_patients` can be `null`. A missing value is never
turned into a number in these fields. `metric_flags` says what each one means:

| Flag | Meaning |
|---|---|
| `reported` | The value is in the response |
| `imputed` | Not published. Scores use the median of the provider's specialty instead, and the score component says `"imputed": true` (quality and experience only) |
| `not_reported` | Not published, and not part of any score (complication and readmission rates) |

A CMS provider with no MIPS score:

```json
{
  "npi": "1234567890",
  "data_source": "cms",
  "quality_score": null,
  "years_experience": 22,
  "accepting_new_patients": null,
  "metric_flags": { "quality_score": "imputed", "years_experience": "reported", "complication_rate": "not_reported", "readmission_rate": "not_reported" }
}
```

## `GET /providers/{provider_id}`

One provider, with everything in the list item plus location, volume, outcome rates, and
the conditions they treat (ordered by name; always empty for CMS data). `provider_id` must be a positive integer.
Missing → `404`, invalid → `422`.

`GET /providers/444`:

```json
{
  "id": 444,
  "npi": null,
  "data_source": "synthetic",
  "display_name": "Dr. Eric Alexander, MD",
  "specialty": { "slug": "cardiology", "name": "Cardiology" },
  "subspecialty": null,
  "city": "New York",
  "state": "NY",
  "years_experience": 18,
  "quality_score": 73.7,
  "cost_index": 0.89,
  "accepting_new_patients": true,
  "metric_flags": { "quality_score": "reported", "years_experience": "reported", "complication_rate": "reported", "readmission_rate": "reported" },
  "zip_code": "10046",
  "latitude": 40.617991,
  "longitude": -74.157242,
  "patient_volume": 627,
  "complication_rate": 0.0464,
  "readmission_rate": 0.1285,
  "conditions": [
    { "slug": "atrial-fibrillation", "name": "Atrial Fibrillation" },
    { "slug": "heart-failure", "name": "Heart Failure" },
    { "slug": "heart-valve-disease", "name": "Heart Valve Disease" },
    { "slug": "hypertension", "name": "Hypertension" }
  ]
}
```

`patient_volume` is annual patients (CMS: Medicare beneficiaries only). `complication_rate` and `readmission_rate` are
fractions (`0.0464` = 4.64%).

### Scored detail

Pass `priority` to also get the score and explanation that a search with the same settings
would give. The numbers are identical to that provider's `POST /search` result, so a detail
page opened from the results can show the same breakdown.

| Param | Type | Notes |
|---|---|---|
| `priority` | `balanced` \| `quality` \| `cost` \| `experience` \| `distance`, optional | Adds `score`, `explanation`, and `distance_miles` to the response. `distance` without `city` + `state` → `422 INVALID_SEARCH` |
| `city`, `state` | string + 2 letters, optional | Must be given together (`422` otherwise). Unknown city → `422 LOCATION_NOT_FOUND`, even without `priority` |
| `radius_miles` | number 1–100, optional | Default `25`, as in search. Requires `city` and `state` |

Without `priority` the response is exactly the plain detail above, with no score fields.
Without a location, `distance_miles` is `null` and the score has no distance component.

`GET /providers/620?priority=quality&city=New York&state=NY` (detail fields trimmed):

```json
{
  "id": 620,
  "npi": null,
  "data_source": "synthetic",
  "display_name": "Dr. Kevin Hill, MD",
  "distance_miles": 14.4,
  "score": {
    "overall": 80.5,
    "components": [
      { "name": "quality", "raw": 79.8, "normalized": 0.798, "weight": 0.55, "contribution": 43.9, "imputed": false },
      { "name": "experience", "raw": 29.0, "normalized": 0.99, "weight": 0.2, "contribution": 19.8, "imputed": false },
      { "name": "cost", "raw": 0.91, "normalized": 0.59, "weight": 0.05, "contribution": 2.9, "imputed": false },
      { "name": "volume", "raw": 0.963, "normalized": 0.963, "weight": 0.1, "contribution": 9.6, "imputed": false },
      { "name": "distance", "raw": 14.372, "normalized": 0.425, "weight": 0.1, "contribution": 4.3, "imputed": false }
    ]
  },
  "explanation": "Stands out for high patient volume within the specialty (busier than 96% of cardiologists). 29 years of experience, 14.4 miles away, cost 9% below average."
}
```

## `POST /search`

Ranked search with structured criteria. See [ranking.md](ranking.md) for how scores are
computed. The body never contains free text, and unknown fields are rejected.

| Field | Type | Notes |
|---|---|---|
| `specialty` | slug, optional | Unknown → `422 INVALID_SEARCH` |
| `condition` | slug, optional | Providers who treat it. Unknown → `422 INVALID_SEARCH`. On a dataset without conditions → `422 CONDITIONS_UNAVAILABLE` |
| `location` | `{ "city", "state" }`, optional | From `GET /cities`; city is case-insensitive. Unknown → `422 LOCATION_NOT_FOUND` |
| `radius_miles` | number 1–100 | Default `25`. Sending it without `location` → `422` |
| `min_quality_score` | number 0–100, optional | Only providers with a reported score match; an imputed median never passes |
| `min_years_experience` | int 0–70, optional | Likewise, reported values only |
| `accepting_new_patients` | bool, optional | |
| `priority` | `balanced` \| `quality` \| `cost` \| `experience` \| `distance` | Default `balanced`. Picks the weight profile, so it changes the scores. `distance` requires `location` |
| `sort` | `match` \| `quality` \| `experience` \| `distance` \| `cost` | Default `match`. Only picks the ordering column. `distance` requires `location` |
| `page` | int ≥ 1 | Default `1` |
| `page_size` | int 1–50 | Default `20` |
| `source` | `manual` \| `nl` | Default `manual`. Whether the criteria came from the form or the AI parser |
| `parser_used` | `llm` \| `rule_based`, optional | Which parser produced the criteria, from `/ai/parse-query`. Only allowed with `"source": "nl"` (`422` otherwise) |

Sort orders: `match` by overall score, `quality` and `experience` highest first, `cost`
cheapest first, `distance` nearest first. Sorting by `quality` or `experience` lists
providers whose value is imputed after everyone with a reported one. Ties always fall back
to overall score, then quality, then provider id.

`priority` or `sort` set to `distance` without a `location` is rejected rather than
silently ignored. Every problem with the criteria is reported at once:

```json
{
  "error": {
    "code": "INVALID_SEARCH",
    "message": "Invalid search criteria; see details",
    "request_id": "…",
    "details": [
      { "field": "sort", "message": "sort=distance requires a location" },
      { "field": "specialty", "message": "Unknown specialty" }
    ]
  }
}
```

With a location, only providers within `radius_miles` (great-circle distance from the
city center) are returned.

Request:

```json
{
  "specialty": "cardiology",
  "condition": "heart-failure",
  "location": { "city": "New York", "state": "NY" },
  "radius_miles": 25,
  "priority": "quality",
  "page_size": 2
}
```

Response (first item only):

```json
{
  "items": [
    {
      "provider": {
        "id": 620,
        "npi": null,
        "data_source": "synthetic",
        "display_name": "Dr. Kevin Hill, MD",
        "specialty": { "slug": "cardiology", "name": "Cardiology" },
        "subspecialty": "Echocardiography",
        "city": "New York",
        "state": "NY",
        "years_experience": 29,
        "quality_score": 79.8,
        "cost_index": 0.91,
        "accepting_new_patients": true,
        "metric_flags": { "quality_score": "reported", "years_experience": "reported", "complication_rate": "reported", "readmission_rate": "reported" }
      },
      "distance_miles": 14.4,
      "score": {
        "overall": 80.5,
        "components": [
          { "name": "quality", "raw": 79.8, "normalized": 0.798, "weight": 0.55, "contribution": 43.9, "imputed": false },
          { "name": "experience", "raw": 29.0, "normalized": 0.99, "weight": 0.2, "contribution": 19.8, "imputed": false },
          { "name": "cost", "raw": 0.91, "normalized": 0.59, "weight": 0.05, "contribution": 2.9, "imputed": false },
          { "name": "volume", "raw": 0.963, "normalized": 0.963, "weight": 0.1, "contribution": 9.6, "imputed": false },
          { "name": "distance", "raw": 14.372, "normalized": 0.425, "weight": 0.1, "contribution": 4.3, "imputed": false }
        ]
      },
      "explanation": "Stands out for high patient volume within the specialty (busier than 96% of cardiologists). 29 years of experience, 14.4 miles away, cost 9% below average."
    }
  ],
  "page": 1,
  "page_size": 2,
  "total": 15,
  "total_pages": 8,
  "priority": "quality",
  "sort": "match",
  "weights_used": { "quality": 0.55, "experience": 0.2, "cost": 0.05, "volume": 0.1, "distance": 0.1 }
}
```

- `score.overall` and `contribution` are rounded to 0.1, `normalized`, `weight` and `raw`
  to 0.001, and `distance_miles` to 0.1. Because of the rounding, the contributions can
  add up to 0.1 more or less than `overall`.
- `raw` is the provider's own value for that component: quality score, years, cost
  index, volume percentile within the specialty, or miles. When `imputed` is true, `raw`
  is the specialty median standing in for a missing value, and the explanation says the
  value wasn't reported instead of calling it a standout.
- The explanation leads with the provider's standout: the factor where they rank highest
  among all providers in their specialty, if they beat at least 80% of them (see
  [ranking.md](ranking.md#explanations)). These peer ranks only shape the wording; they
  never change scores or order.
- `weights_used` are the weights actually applied. Without a location there is no
  distance weight, and the rest are rescaled to sum to 1. For example, `{"priority": "cost"}`
  gives `{ "quality": 0.294, "experience": 0.118, "cost": 0.529, "volume": 0.059 }`.

Every successful search writes a `search_logs` row with the source, parser used, specialty,
state, priority, result count, and latency. It never stores the condition, city, or any text.

Errors:

```json
{
  "error": {
    "code": "LOCATION_NOT_FOUND",
    "message": "Location not found; choose a city from GET /cities",
    "request_id": "6a747a02-27ab-45f1-ab57-3aebc07729a5",
    "details": [{ "field": "location", "message": "Unknown city" }]
  }
}
```

```json
{
  "error": {
    "code": "INVALID_SEARCH",
    "message": "Invalid search criteria; see details",
    "request_id": "f57c1acb-efab-4d0c-84d1-78603d9c5e9e",
    "details": [{ "field": "specialty", "message": "Unknown specialty" }]
  }
}
```

## `GET /ranking/weights`

The weight profile for each priority, served straight from the ranking engine's
`PROFILES` (`ranking/weights.py`), so it can't drift from how results are actually ranked.
The methodology page renders its weight table from this. Each profile sums to 1, and no
profile gives quality less than `min_quality_weight`.

```json
{
  "profiles": {
    "balanced": { "quality": 0.35, "experience": 0.2, "cost": 0.15, "volume": 0.15, "distance": 0.15 },
    "quality": { "quality": 0.55, "experience": 0.2, "cost": 0.05, "volume": 0.1, "distance": 0.1 },
    "cost": { "quality": 0.25, "experience": 0.1, "cost": 0.45, "volume": 0.05, "distance": 0.15 },
    "experience": { "quality": 0.25, "experience": 0.45, "cost": 0.1, "volume": 0.1, "distance": 0.1 },
    "distance": { "quality": 0.25, "experience": 0.1, "cost": 0.1, "volume": 0.05, "distance": 0.5 }
  },
  "min_quality_weight": 0.25
}
```

These are the base weights. A search without a location drops distance and divides the
rest by their sum; its `weights_used` shows the result (see [ranking.md](ranking.md)).

## `POST /ai/parse-query`

Turns a natural-language query into search criteria. It never runs a search. The
frontend shows the criteria as editable fields, and the user then runs `POST /search` with
them. Parsing never fails because of the AI: if the model is unavailable, slow, or returns
anything invalid, the keyword parser answers instead, and a warning says so.

Request:

```json
{ "query": "Find me a highly rated cardiologist near New York with experience treating heart failure" }
```

`query` is trimmed and must be 1–500 characters (`422` otherwise). Unknown fields are
rejected.

Response:

```json
{
  "criteria": {
    "specialty": "cardiology",
    "condition": "heart-failure",
    "location": { "city": "New York", "state": "NY" },
    "radius_miles": null,
    "min_quality_score": null,
    "min_years_experience": null,
    "accepting_new_patients": null,
    "priority": "quality"
  },
  "parser_used": "rule_based",
  "warnings": []
}
```

- **`criteria`** uses exactly the field names and value shapes of the `POST /search`
  body, and every value is one the directory knows. Send the non-null fields to
  `/search` along with `"source": "nl"` and `"parser_used": <parser_used>`.
- **`parser_used`**: `llm` when the AI parser answered, and `rule_based` when the keyword
  parser did. That happens when `AI_PROVIDER=none` or no key is configured, or as a
  fallback.
- **`warnings`** are human-readable notes to show next to the criteria: a fallback, a
  specialty inferred from the condition, or a value dropped because it wasn't in the
  directory. They never repeat the query or a rejected value.

For example, `"who treats heart failure? nearest one please"` gives:

```json
{
  "criteria": {
    "specialty": "cardiology",
    "condition": "heart-failure",
    "location": null,
    "radius_miles": null,
    "min_quality_score": null,
    "min_years_experience": null,
    "accepting_new_patients": null,
    "priority": null
  },
  "parser_used": "rule_based",
  "warnings": [
    "Ignored the distance priority because no location was recognized.",
    "Inferred the specialty (Cardiology) from the condition."
  ]
}
```

A radius or distance priority without a recognized location is dropped, because
`/search` would reject it.

This endpoint has its own per-IP limit, `AI_RATE_LIMIT_PER_MINUTE` (default 10), on top
of the global one. Over it you get `429 RATE_LIMITED` with `Retry-After`. The server logs
the parser used, the latency, and the query length, but never the query text.
