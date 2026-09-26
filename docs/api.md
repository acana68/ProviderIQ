# ProviderIQ API

All endpoints are under `/api/v1`. Responses are JSON. Interactive docs (OpenAPI) are at
`/docs` when the server is running.

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

Validation errors also include `details`, one entry per invalid field. The submitted value
is never echoed back.

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
| `VALIDATION_ERROR` | 422 | Invalid query or path parameter |
| `RATE_LIMITED` | 429 | Over `RATE_LIMIT_PER_MINUTE` (default 120). Wait `Retry-After` seconds |
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
      "display_name": "Dr. Eric Alexander, MD",
      "specialty": { "slug": "cardiology", "name": "Cardiology" },
      "subspecialty": null,
      "city": "New York",
      "state": "NY",
      "years_experience": 18,
      "quality_score": 73.7,
      "cost_index": 0.89,
      "accepting_new_patients": true
    },
    {
      "id": 1332,
      "display_name": "Dr. Holly Blair, MD",
      "specialty": { "slug": "cardiology", "name": "Cardiology" },
      "subspecialty": "Heart Failure",
      "city": "New York",
      "state": "NY",
      "years_experience": 3,
      "quality_score": 68.5,
      "cost_index": 0.88,
      "accepting_new_patients": true
    }
  ],
  "page": 1,
  "page_size": 2,
  "total": 22,
  "total_pages": 11
}
```

`cost_index` is relative to the regional average: `1.0` is average and lower is cheaper.

## `GET /providers/{provider_id}`

One provider, with everything in the list item plus location, volume, outcome rates, and
the conditions they treat (ordered by name). `provider_id` must be a positive integer.
Missing → `404`, invalid → `422`.

`GET /providers/444`:

```json
{
  "id": 444,
  "display_name": "Dr. Eric Alexander, MD",
  "specialty": { "slug": "cardiology", "name": "Cardiology" },
  "subspecialty": null,
  "city": "New York",
  "state": "NY",
  "years_experience": 18,
  "quality_score": 73.7,
  "cost_index": 0.89,
  "accepting_new_patients": true,
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

`patient_volume` is annual patients. `complication_rate` and `readmission_rate` are
fractions (`0.0464` = 4.64%).
