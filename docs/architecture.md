# ProviderIQ — Architecture

## 1. System architecture

```
                 ┌──────────────────────────────┐
  User ───────▶  │  React + TypeScript SPA      │
                 └──────────────┬───────────────┘
                                │ same-origin JSON (/api/v1)
                 ┌──────────────▼───────────────┐
                 │  nginx (Docker) or Vite dev  │
                 │  proxy: /api/ → backend      │
                 └──────────────┬───────────────┘
                 ┌──────────────▼───────────────┐
                 │  FastAPI                     │
                 │  routes → services → repos   │
                 └──┬───────────┬───────────┬───┘
                    │           │           │
          ┌─────────▼──┐  ┌─────▼──────┐  ┌─▼──────────────┐
          │ AI Parser  │  │ Search Svc │  │ Provider/Ref   │
          │ (LLM or    │  │ + Ranking  │  │ Repositories   │
          │  fallback) │  │   Engine   │  └──────┬─────────┘
          └─────┬──────┘  └─────┬──────┘         │
                │               └───────┬────────┘
          LLM API (text in,       ┌─────▼──────┐
          JSON out, no DB)        │ PostgreSQL │
                                  └────────────┘
```

### Key decisions

- **Parsing and searching are two separate calls.** The frontend calls `POST /ai/parse-query`, shows the parsed filters as editable fields, and then calls `POST /search` with structured criteria. `/search` never sees free text and never touches the LLM, so the search path is fully deterministic and testable. It also gives "let the user fix what the AI got wrong" for free.
- **The app runs with no API key.** `AI_PROVIDER=none` uses a rule-based parser. Anyone can clone the repo, run `docker compose up`, and everything works.
- **Explanations are template-based, not LLM-generated.** They're built from the score breakdown, the provider's own numbers, and where the provider ranks among specialty peers, e.g. *"Stands out for high patient volume within the specialty (busier than 96% of cardiologists). 29 years of experience, 14.4 miles away, cost 9% below average."* That makes them free, instant, testable, and impossible to hallucinate. The first version led with the largest contribution (*"Ranked mainly on quality (48.4 of 81.5 points)"*), which mostly restated the weights; [ranking.md](ranking.md#explanations) has the story. An LLM rewrite is a stretch goal.
- **Scores don't depend on who else matched.** Normalization uses fixed bounds or specialty-wide distributions, never min-max over the current result set. A provider's score is the same whether 5 or 500 others matched. This is what makes the detail page and the explanations consistent (see section 7).
- **Location lookup comes from a local `cities` table, not a geocoding API.** The synthetic providers are clustered around 25 cities, and the user's location resolves against that same table. No external dependency, no API cost. The real-data option swaps in 65 New Jersey municipalities with Census coordinates (section 10).
- **Two datasets, one app.** Synthetic data is the default and what tests and CI use. `DATA_SOURCE=cms_nj` seeds real public CMS data for New Jersey instead. The app reads which one is loaded from the database, not from the setting (section 10).
- **Dev workflow is Postgres in Docker, with backend and frontend run natively.** Faster reloads and easier debugging on Windows. Full `docker compose up` is the one-command demo and the CI path.
- **The browser only ever talks to one origin.** The frontend calls relative `/api/v1/...` URLs. In development the Vite dev server proxies them to uvicorn; in Docker, nginx does. The planned AWS setup does the same with CloudFront. So production needs no CORS, and the frontend has nothing environment-specific in it.

### Configuration and ports

All settings come from environment variables, read by `app/core/config.py` (pydantic-settings) with the **repo-root `.env`** as a fallback. `.env.example` lists every variable. `.env` is never committed and never copied into an image; Compose passes it in at runtime.

| Port (host) | What | Notes |
|---|---|---|
| 5173 | Vite dev server | Local dev only; proxies `/api` to 8000 |
| 8080 | nginx (frontend container) | The Docker app; proxies `/api/` to `backend:8000` |
| 8000 | FastAPI (uvicorn) | Local dev and Docker (127.0.0.1 only); OpenAPI docs at `/docs`, except in prod |
| 5433 | PostgreSQL 17 | Host port for local tools and tests (127.0.0.1 only); `db:5432` inside Compose. 5433 avoids clashing with a native Postgres |

The dev database (`provideriq`) and the test database (`provideriq_test`, created by `db/init/01-create-test-db.sql` on first init) live in the same container. Tests refuse to run unless `TEST_DATABASE_URL` points at a separate database.

Two database roles. The owner (`POSTGRES_USER`, `MIGRATION_DATABASE_URL`) runs migrations, seeding and the CMS pipeline. The API connects as `provideriq_app` (`DATABASE_URL`), which a migration creates with `SELECT` on the app's tables and `INSERT` on `search_logs` only; `scripts/app_db_role.py` gives it its login password, outside the migrations. `tests/integration/test_db_roles.py` checks its exact privileges.

## 2. MVP feature set

**In:**

- Structured search: specialty, condition, location + radius, min quality, min experience, ranking priority
- Sorting, pagination, deterministic tie-breaking
- Ranking engine with a per-component score breakdown
- Natural-language parsing with an LLM, plus a rule-based fallback
- Provider detail page with metrics, conditions, score breakdown, and explanation
- Reference endpoints for the specialty, condition, and city dropdowns
- Synthetic data generator (1,500 providers, 10 specialties, 50 conditions, 25 cities; seeded, so reproducible) and seed script
- Search logging with no free text and no identifiers
- Consistent JSON errors, structured logging, CORS, body size limit, rate limiting
- Backend and frontend tests, Docker Compose, GitHub Actions CI
- AWS deployment: **deferred** to avoid running costs. The containers, health checks, proxy headers and smoke test are ready for it (see section 9)
- Methodology page and a disclaimer on every page
- A plain-language privacy page, crisis helpline information when a query calls for it, and a layout checked at phone width

**Out (post-MVP):**

- Elasticsearch, Redis, Airflow, dbt, Kubernetes
- User accounts and auth
- `POST /providers` — an admin write endpoint needs auth to be done properly, so data comes in through the seed script instead
- LLM-written explanations
- Maps UI

## 3. Backend structure

The layers are strict. Routes handle HTTP only. Services hold business logic. Repositories are the only code that touches SQLAlchemy. `ai/` never imports anything from `repositories/`, `models/` or `database/`, and that separation is itself a security property. `tests/unit/test_architecture.py` enforces these boundaries, including indirect imports.

```
backend/app/
├── main.py              # app factory: middleware, routers, error handlers
├── api/
│   ├── deps.py          # DB session, services, parser injection
│   └── routes/          # health, reference (specialties, conditions, cities), providers,
│                        # search, ai, ranking (weights)
├── core/                # config (pydantic-settings), errors, logging, middleware,
│                        # rate_limit, request_context (request ID)
├── database/            # engine/session, declarative Base
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response models (closed: extra="forbid" on input)
├── repositories/        # all queries live here, including the peer-percentile window functions
├── services/
│   ├── search_service.py   # orchestrates filter → distance → rank → paginate → log
│   ├── geo.py              # haversine + bounding box
│   ├── explanation.py      # templated explanations with peer percentiles
│   └── ranking/            # normalization.py, weights.py, engine.py (pure functions)
└── ai/
    ├── base.py             # QueryParser protocol
    ├── vocabulary.py       # allowed slugs/cities, loaded via a protocol (no repository import)
    ├── criteria.py         # final checks shared by both parsers
    ├── llm_client.py       # provider-specific client behind an interface
    ├── llm_parser.py
    ├── rule_based_parser.py
    ├── prompts.py
    ├── crisis.py           # keyword check for suicide / self-harm risk (crisis flag)
    └── factory.py          # picks the parser from AI_PROVIDER env var
```

The ranking engine is pure Python: no database, no FastAPI. That makes it the easiest thing in the project to unit test exhaustively.

## 4. Frontend structure

```
frontend/src/
├── main.tsx, App.tsx          # router setup
├── pages/                     # SearchPage, ResultsPage, ProviderDetailPage, MethodologyPage, PrivacyPage,
│                              # NotFoundPage
├── components/
│   ├── layout/                # AppLayout, Disclaimer, ErrorBoundary, DatasetBanner, CrisisBanner (+ providers)
│   ├── search/                # NaturalLanguageSearch, CriteriaEditor, PriorityControl, exampleQueries
│   ├── results/               # ProviderCard, ResultsToolbar, Pagination, ScoreBar, ScoreLegend, SearchSummary
│   ├── provider/              # ScoreBreakdownTable
│   └── common/                # LoadingState, ErrorState, EmptyState, TableScroll
├── services/                  # apiClient (fetch wrapper + error parsing), aiApi, providerApi,
│                              # rankingApi, referenceApi, searchApi
├── hooks/                     # useApiData (shared fetch/abort/state), useSearch, useProvider, useReferenceData
├── types/                     # api.ts, provider.ts, ranking.ts, search.ts
├── utils/                     # searchParams (URL ⇄ criteria), criteria, format, labels, navigation, pagination
└── styles/                    # tokens.css (colors/spacing vars), global.css

frontend/tests/                # Vitest + React Testing Library, one file per page or module
frontend/e2e/                  # Playwright browser checks (375px layout, link crawl), API mocked
frontend/scripts/screenshots.ts  # Playwright: README screenshots from the running Docker stack
frontend/scripts/og-image.ts     # Playwright: the link-preview image (public/og-image.png)
```

The pages, and what each one does:

| Route | Page |
|---|---|
| `/` | Natural-language box (Interpret) above the editable criteria form. Interpret only fills the form; Search navigates to `/results` |
| `/results?...` | Summary of the search, sort and priority controls, score legend, provider cards with stacked score bars, pagination |
| `/providers/:id?...` | Header, match score with explanation and a priority switcher, score bar and breakdown table, metrics, conditions treated |
| `/methodology` | How AI is used, the five factors, the weight table (from `GET /ranking/weights`), how standouts are picked, limitations |

Choices:

- **`fetch` with a thin wrapper, not Axios.** One less dependency, and there's nothing Axios gives us here.
- **Plain custom hooks, not TanStack Query.** Writing loading and error state by hand is the point. TanStack Query is a good "what I'd change" answer later.
- **CSS Modules** (`ProviderCard.module.css` next to each component) plus design tokens.
- **Search state lives in the URL** (`/results?specialty=cardiology&city=...`). Results survive refresh, can be shared, and the back button works.
- **TS types are hand-written** to mirror the Pydantic schemas. Generating them from FastAPI's OpenAPI spec is a later upgrade.

## 5. PostgreSQL schema

```
specialties          id PK, slug UNIQUE, name UNIQUE
conditions           id PK, slug UNIQUE, name UNIQUE
cities               id PK, name, state, latitude, longitude   UNIQUE(name, state)
providers            id PK, npi UNIQUE (CMS only), data_source ('synthetic'|'cms'),
                     first_name, last_name, credential (MD/DO),
                     specialty_id FK → specialties, subspecialty (nullable text),
                     city, state, zip_code, latitude, longitude,
                     years_experience INT NULL,
                     quality_score DOUBLE NULL (0–100),
                     quality_imputed BOOL (generated: quality_score IS NULL),
                     cost_index DOUBLE (1.00 = regional avg, lower = cheaper),
                     patient_volume INT (annual patients),
                     complication_rate DOUBLE NULL (0–1), readmission_rate DOUBLE NULL (0–1),
                     accepting_new_patients BOOL NULL,
                     created_at, updated_at
provider_conditions  provider_id FK, condition_id FK   PK(provider_id, condition_id)
search_logs          id PK, created_at, source ('nl'|'manual'), parser_used,
                     specialty_id, state, priority, result_count, latency_ms
dataset_metadata     id PK (always 1), source ('synthetic'|'cms_nj'), as_of, vintage,
                     seeded_at
staging.*            the CMS pipeline's raw text tables and SQL transforms (section 10)
```

Why it's shaped this way:

- **Specialties get their own table.** They're a fixed vocabulary that feeds the dropdown. The foreign key prevents "Cardiology" vs "cardiology" drift, and the LLM's output gets validated against the same list.
- **Subspecialty stays as text.** It's sparse and only displayed, so a table would be over-normalizing.
- **Conditions need their own tables** because the relationship is many-to-many. There's no specialty column on conditions. "Which conditions go with cardiology" is derived by joining through the providers who treat them, so there's no extra table to keep in sync.
- **`cost_index` replaces `cost_score`.** "Cost score" is ambiguous: does high mean cheap or expensive? An index where 1.0 is average removes the ambiguity. Normalization turns it into cost efficiency.
- **`quality_score` is stored as a given rating.** It's generated to correlate with low complication and readmission rates, which are shown on the detail page. In a real system a data pipeline would compute this score from claims data (a natural hook for dbt later).
- **`search_logs` stores no query text and no condition.** People type their own health details into search boxes, so neither gets logged.
- **Missing metrics are NULL, never 0.** Real data doesn't publish everything, and a 0 would be a (terrible) score. `quality_imputed` is a generated column, so it can never disagree with `quality_score`. `accepting_new_patients` has no default: an unknown value must not quietly read as "accepting".

### Indexes

| Index | Why |
|---|---|
| `providers(specialty_id, state)` | Almost every search filters by specialty. The composite also covers specialty+state. |
| `providers(latitude, longitude)` | Supports the radius bounding-box prefilter. |
| `provider_conditions(condition_id)` | The primary key starts with `provider_id`, so "who treats X" needs the reverse direction. |
| `search_logs(created_at)` | Time-range queries for observability. |

No `quality_score` index: a minimum-quality filter usually matches most rows, so an index wouldn't help.

Checked with `EXPLAIN` on the seeded data (after `ANALYZE`): a specialty plus bounding-box query already uses both provider indexes, combined with a `BitmapAnd`, and a condition lookup uses `provider_conditions(condition_id)`. At 1,500 rows (a 264 kB table) the difference is negligible, but the plans are the ones that matter as the table grows.

Integrity is enforced in the database too, not only in Pydantic: `CHECK` constraints on the providers table cover quality 0–100, rates 0–1, years 0–70, a positive cost index, non-negative volume, valid coordinates, and `credential IN ('MD', 'DO')`, and `search_logs.source` is constrained to `nl`/`manual`. The range checks pass for NULL, so they still bound every value that is present. A CMS row must have a 10-digit NPI and a synthetic row must not (`(data_source = 'cms') = (npi IS NOT NULL)`).

## 6. REST API (`/api/v1`)

The full reference, with real examples, is [api.md](api.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness; never touches the DB; not rate limited |
| GET | `/health/ready` | Readiness: DB ping (503 when the DB is down) |
| GET | `/specialties` | Dropdown data, with provider counts |
| GET | `/conditions?specialty=cardiology` | Conditions treated within a specialty |
| GET | `/cities` | The locations a search can use (the local geocoding table) |
| GET | `/dataset` | Which dataset is loaded, what it publishes, and its disclaimer |
| GET | `/providers?specialty=&state=&city=&accepting_new_patients=&page=&page_size=` | Browse without ranking |
| GET | `/providers/{id}?priority=&city=&state=&radius_miles=` | Detail; adds score + explanation when a priority is passed |
| POST | `/search` | Ranked search with structured criteria |
| GET | `/ranking/weights` | The weight profiles, straight from `ranking/weights.py` (the methodology page renders them) |
| POST | `/ai/parse-query` | Natural language → criteria (never runs a search) |

`POST /search` request:

```json
{
  "specialty": "cardiology",
  "condition": "heart-failure",
  "location": { "city": "New York", "state": "NY" },
  "radius_miles": 25,
  "min_quality_score": null,
  "min_years_experience": null,
  "priority": "balanced",
  "sort": "match",
  "page": 1,
  "page_size": 20
}
```

Each result:

```json
{
  "provider": { "id": 620, "display_name": "Dr. Kevin Hill, MD", "specialty": { "slug": "cardiology", "name": "Cardiology" }, "...": "..." },
  "distance_miles": 14.4,
  "score": {
    "overall": 80.5,
    "components": [
      { "name": "quality", "raw": 79.8, "normalized": 0.798, "weight": 0.55, "contribution": 43.9 }
    ]
  },
  "explanation": "Stands out for high patient volume within the specialty (busier than 96% of cardiologists). 29 years of experience, 14.4 miles away, cost 9% below average."
}
```

The response also carries the pagination fields, `priority`, `sort`, and `weights_used` (the weights actually applied, after renormalization).

Error format is always `{"error": {"code", "message", "request_id", "details?"}}`. `details` lists one entry per bad field and never echoes the submitted value.

| Code | Status |
|---|---|
| `BAD_REQUEST` | 400 (e.g. an invalid `Content-Length`) |
| `NOT_FOUND` | 404 (unknown route, provider, or specialty slug) |
| `METHOD_NOT_ALLOWED` | 405 (with an `Allow` header) |
| `PAYLOAD_TOO_LARGE` | 413 (body over `MAX_REQUEST_BODY_BYTES`, default 64 KiB) |
| `VALIDATION_ERROR` | 422 (malformed parameter or body field, unknown field) |
| `INVALID_SEARCH` | 422 (well-formed but unusable: unknown slug, or distance priority/sort without a location) |
| `LOCATION_NOT_FOUND` | 422 (city not in `GET /cities`) |
| `CONDITIONS_UNAVAILABLE` | 422 (a condition filter on a dataset without condition data) |
| `RATE_LIMITED` | 429 (with `Retry-After`) |
| `INTERNAL_ERROR` | 500 (no stack traces leaked; details go to the server log with the request ID) |

There's no "AI unavailable" error, because that case falls back instead of failing.

**Priority vs sort:** `priority` changes how the match score is computed. `sort` just picks the column to order by (match score, quality, experience, distance, or cost). They're kept separate on purpose so the UI isn't confusing.

## 7. Ranking system

**Step 1: normalize every component to [0, 1], where higher is better.**

| Component | Formula | Reasoning |
|---|---|---|
| Quality | `q = quality_score / 100` | Already on a fixed 0–100 scale. |
| Experience | `e = min(1, ln(1+years) / ln(31))` | Diminishing returns: 2→10 years matters more than 20→28. 5y → 0.52, 10y → 0.70, 20y → 0.89, 30y+ → 1.0 |
| Cost efficiency | `c = clamp(1.5 − cost_index, 0, 1)` | Maps an index range of 0.5–1.5 onto 1–0, so average cost (1.0) scores 0.5. Synthetic data only: CMS spending per patient is scored as a within-specialty percentile ([ranking.md](ranking.md#cms-spending-is-scored-as-a-percentile)). |
| Volume | `v = percent_rank within specialty` | Primary care sees far more patients than oncology, so raw counts can't be compared across specialties. Computed with a SQL window function over the whole specialty, not the filtered results. |
| Distance | `d = 1 − distance / radius` | Everything returned is inside the radius, so this falls in [0, 1] with a linear falloff. |

**Step 2: weighted sum.**

```
overall       = 100 × Σ(wᵢ·sᵢ) / Σ(wᵢ)     over active components
contributionᵢ = 100 × wᵢ·sᵢ / Σ(wᵢ)        → contributions sum exactly to overall
```

If there's no location, the distance component is dropped and the remaining weights are renormalized automatically.

**Step 3: pick the weight profile based on priority.** Profiles live in `ranking/weights.py` as validated config; startup fails if any profile doesn't sum to 1.

| Priority | Quality | Experience | Cost | Volume | Distance |
|---|---|---|---|---|---|
| balanced | .35 | .20 | .15 | .15 | .15 |
| quality | .55 | .20 | .05 | .10 | .10 |
| cost | .25 | .10 | .45 | .05 | .15 |
| experience | .25 | .45 | .10 | .10 | .10 |
| distance | .25 | .10 | .10 | .05 | .50 |

Quality never drops below 0.25. That's deliberate: even a cost-focused search shouldn't put a poor-quality provider on top.

**Worked example** (quality priority): quality 88, 15 years, cost 0.9, volume at the 70th percentile, 6 mi away with a 20 mi radius.

| Component | Weight × normalized | Contribution |
|---|---|---|
| Quality | .55 × .88 | 48.4 |
| Experience | .20 × .81 | 16.1 |
| Cost | .05 × .60 | 3.0 |
| Volume | .10 × .70 | 7.0 |
| Distance | .10 × .70 | 7.0 |
| **Overall** | | **81.5** |

**Tie-break order:** overall descending, then quality descending, then id ascending. Without a stable order, a provider could show up on two different pages.

**Search pipeline:**

1. Resolve the city to lat/lon.
2. SQL filters: specialty, condition join, minimums, and a bounding box from the radius.
3. Compute exact haversine distance in Python and drop anything outside the radius.
4. Score, sort, and paginate. Each candidate's peer percentiles come from `percent_rank()` windows over its whole specialty, fetched in the same query as the candidates. Only volume's percentile enters the score.
5. Build explanations for the returned page only, using the peer percentiles.
6. Log the search (no text, no condition, no city).

Ranking the full filtered set in Python is fine at this scale. At 100M providers, scoring moves into the database or Elasticsearch.

## 8. How AI is used

The LLM does exactly one job: it turns a patient's sentence into the same structured
criteria the search form produces. Everything else stays deterministic code.

```
"cardiologist near NYC for heart failure, quality matters"
      │  POST /ai/parse-query   (1–500 chars, own rate limit)
      ▼
QueryParser.parse(text) → ParseResult { criteria, parser_used, warnings }
      │
      ├─ LLMQueryParser (AI_PROVIDER=anthropic and a key is set)
      │    Claude, forced tool use → ParsedCriteria → vocabulary check
      │
      └─ RuleBasedQueryParser (AI_PROVIDER=none, no key, or any LLM failure)
      ▼
Frontend shows editable criteria → user clicks Search → POST /search (structured only)
```

- **Parse only.** `/ai/parse-query` never searches, and `/search` never sees free text or
  calls the LLM. Ranking stays deterministic and testable, and the user can fix what the
  AI got wrong before searching.
- **Forced tool use.** The request defines a single tool whose `input_schema` is the
  `ParsedCriteria` JSON schema, and `tool_choice` forces that tool. So the reply is always
  one tool call whose input is the criteria object; no free-form text is parsed. The tool
  is never executed; it is only a typed container for the answer. The request also uses
  temperature 0, a 512-token cap, and the `AI_TIMEOUT_SECONDS` timeout with no retries.
- **Validation, twice.**
  - First, the output must validate against `ParsedCriteria`: a closed schema
    (`extra="forbid"`), enums, and bounded ranges. The same shapes as `SearchRequest`.
  - Then every specialty, condition, and city is checked against the vocabulary loaded
    from the database. Unknown values are dropped with a warning that doesn't repeat them.
  - Last, a radius or distance priority without a location is dropped, because `/search`
    would reject it.
- **Fallback, always.** Any failure falls back to the keyword parser: a timeout, API
  error, refusal, truncated or malformed output, or an extra field. The response still
  succeeds, with `parser_used: "rule_based"` and the warning "AI parser unavailable; used
  keyword matching instead." With `AI_PROVIDER=none` (the default), or `anthropic` without
  a key (warned at startup), the app runs entirely without AI.
- **Symptoms aren't conditions.** The prompt sets a condition only when the query names
  one, never from symptoms: "chest pain" leaves it null. A symptom is not a diagnosis, and a
  condition filter would narrow the results to specialists in that one condition.
- **Crisis support.** `crisis` in the parse response is true when the query suggests
  suicide or self-harm risk: a short keyword list (`ai/crisis.py`) checked in the route on
  every parse, or an optional `crisis` flag in the LLM's answer schema (`LLMParsedQuery`);
  either one is enough. The frontend shows the 988 Suicide & Crisis Lifeline above the
  page for the rest of the visit. It never changes the criteria or blocks the search.
- **Injection containment.**
  - The query is escaped and wrapped in `<query>` tags. The system prompt says it is data
    to interpret, not instructions.
  - Detection isn't what we rely on. The model has no data access, no executable tools,
    and nothing secret in its prompt, and it can only answer through the criteria schema.
  - So the worst a successful injection can do is produce some other valid search.
  - `ai/` is forbidden from importing repositories, models, or the database, which a test
    enforces. The LLM has no path to data.
- **Privacy.**
  - The query text is never logged, stored, or echoed in warnings. The parse log line has
    only the parser used, the latency, the query length, and the warning count; not the
    crisis flag either.
  - LLM failures log only the exception type, because exception messages can quote the
    output.
  - `search_logs` records `parser_used`, never the text.
  - The API key is a `SecretStr`, so it is never printed.
- **Cost controls.**
  - Claude Haiku 4.5 by default (`AI_MODEL`).
  - A 512-token output cap and no retries.
  - A per-IP limit on this endpoint (`AI_RATE_LIMIT_PER_MINUTE`, default 10), checked
    before any database or API work.
  - The 500-character input limit.
  - Tests use a `FakeLLMClient`. The one test against the real API is marked `live` and
    runs only with `pytest -m live`.

**Measuring it:** `python -m scripts.eval_parser` scores both parsers field by field on
23 labeled queries. It runs the LLM parser only when a key is configured. On the current
set the keyword parser gets 19/23 fully right; the README has the per-field table. The
LLM needs a new run with the current prompt: the previous one (22 queries) got 20 right,
but inferred a condition (coronary artery disease) from the symptom "chest pain". The
prompt now forbids that, and the chest-pain queries check it. The user sees and can edit
every parsed field before searching either way.

**Provider-agnostic design:** `LLMQueryParser` depends on an `LLMClient` interface with a
single method, `complete_json(system, user, schema) -> dict`. Switching providers means
writing one new client class. Forced tool choice and temperature both work on the default
model. Some newer Claude models reject one or the other, which would make every parse
fall back, so re-check `parser_used` after changing `AI_MODEL`.

## 9. Roadmap

| # | Stage | Learning focus |
|---|---|---|
| 1 | Environment setup, repo skeleton, `/health` endpoint, pytest wired up | Python venv, FastAPI basics, project layout |
| 2 | Postgres in Docker, SQLAlchemy models, config, Alembic first migration | Docker basics, ORM, migrations |
| 3 | Synthetic data generator (seeded, correlated metrics) + seed script | Reproducible data, bulk inserts |
| 4 | Repositories, provider/reference endpoints, error format, logging, CORS, size limit, rate limiting | Layering, dependency injection, middleware |
| 5 | Ranking engine as pure functions, with thorough unit tests | Testable design |
| 6 | Search service + `POST /search` + geo + search logging + integration tests | Orchestration, test database setup |
| 7 | AI parser: interface, rule-based fallback, LLM client, endpoint, tests with fake client | Structured outputs, graceful degradation |
| 8 | Frontend setup: Vite, TS strict mode, Router, ESLint/Prettier, layout, API client | React/TS fundamentals |
| 9 | Search page + natural-language box + criteria editor | State, forms, controlled inputs |
| 10 | Results page: cards, sort, filter, pagination, URL state | Data fetching hooks, routing |
| 11 | Provider detail + score breakdown + methodology page | Component composition |
| 12 | Frontend tests (Vitest + React Testing Library) | Testing UI behavior, mocking fetch |
| 13 | Full Docker Compose + GitHub Actions CI | Multi-stage images, CI pipelines |
| 14 | AWS deployment | Cloud basics, networking, secrets |
| 15 | README, docs, screenshots, interview prep | Explaining the system |
| 16a | Real CMS data for New Jersey: ELT pipeline, staging schema, missing-data handling, `GET /dataset` | Public data, SQL transforms, data quality |
| 16b | Frontend for the real dataset: labels, disclaimer, imputed / not-reported flags | |
| 17a | Security fixes: proxy trust, database roles, pinned dependencies, split health checks | Least privilege, supply chain |
| 17b | Polish and responsibility: phone layout, privacy page, crisis support, symptom rule, link checks | Accessibility, safety |

Backend tests get written inside each stage, not saved for the end.

**Status:** stages 1–13, 15, 16a–b and 17a–b are done. Stage 14 (AWS) is deliberately deferred to avoid
running costs; the plan below is ready to execute.

**AWS plan (Stage 14, simplest credible setup):**

- The frontend is built to S3 and served through CloudFront.
- `/api/*` is routed by CloudFront to the FastAPI container on one EC2 instance, with RDS for Postgres.
- Secrets (the database password, the Anthropic key) live in SSM Parameter Store and are passed to the container as environment variables, never baked into an image.
- Everything sits on one HTTPS domain, so production needs no CORS.
- ECS Fargate plus an ALB is the "how I'd scale it" answer rather than a cost paid now.

Already prepared for it:

- **Containers.** Multi-stage images. The backend runs as a non-root user with runtime dependencies only. The frontend runs on unprivileged nginx on 8080.
- **Health checks.** Docker `HEALTHCHECK`s on both images. `/health/live` is liveness; `/health/ready` returns 503 when the database is unreachable, and is what the backend's health check uses.
- **Proxy headers.** uvicorn runs with `--proxy-headers`, trusting `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS`. The default, 127.0.0.1, trusts no other host, so clients can't spoof their IP to dodge the per-IP rate limits. Compose gives nginx a fixed address (`172.29.53.10`) and sets `FORWARDED_ALLOW_IPS` to it; nginx appends its peer to `X-Forwarded-For`, and uvicorn takes the rightmost untrusted entry, which is that peer. A deployment adds its load balancer's addresses.
- **Migrations and seeding at startup.** The entrypoint runs `alembic upgrade head`, sets the runtime role's password, then seeds only if the database is empty, all as the owner role. It then drops the owner's credentials from the environment before starting the API.
- **Smoke test.** `backend/scripts/smoke_test.py` (standard library only) checks a running deployment end to end. The Docker CI workflow already runs it against the full stack.

## 10. Real data (CMS, New Jersey)

Alongside the synthetic data, ProviderIQ can run on real public data: physicians in New
Jersey, in the same 10 specialties, built from three CMS datasets and two Census files.
`DATA_SOURCE=cms_nj` seeds it. Tests and CI stay on synthetic data.

### Sources

| Source | What we take | How it's cut to NJ |
|---|---|---|
| CMS Provider Data Catalog: Doctors and Clinicians **National Downloadable File** (`mj5m-pzi6`) | NPI, name, credential, medical school graduation year, primary specialty, practice address and ZIP | API query, `state = NJ` |
| CMS Provider Data Catalog: **PY 2024 Clinician Overall MIPS Performance** (`a174-a962`) | MIPS final score per NPI | No state column: the national file is downloaded, and filtered to the NDF's NJ NPIs while loading |
| data.cms.gov: **Medicare Physician & Other Practitioners, by Provider**, CY 2024 | Medicare beneficiaries, services, allowed amounts per NPI | API query, `Rndrng_Prvdr_State_Abrvtn = NJ` |
| Census **2025 Gazetteer, ZCTAs** | ZIP code centroids | National file; ZIP prefixes 07/08 kept while loading |
| Census **2025 Gazetteer, county subdivisions (NJ)** and **Vintage 2025 population estimates (NJ)** | The municipalities used as search locations | State files |

Every dataset id is pinned in `pipeline/sources.py`. `data/cms/MANIFEST.json` records each
file's URL, release, download time, row count and SHA-256. A cached file is checked against
that SHA-256 before `pipeline.extract` keeps it and before `pipeline.transform` loads it; a
mismatch stops the run and names the `--refresh` command.

### Pipeline (ELT)

```
python -m pipeline.extract      CMS / Census APIs ──▶ data/raw/        (gitignored, cached)
python -m pipeline.transform    data/raw/ ──COPY──▶ staging.raw_*      (text, as downloaded)
                                staging.raw_* ──sql/00…07──▶ staging.cms_providers,
                                                              staging.cms_cities
                                ──▶ data/cms/providers_nj.csv, cities_nj.csv  (committed)
                                ──▶ docs/data-quality.md
python -m scripts.seed_db --source cms_nj   data/cms/ ──▶ providers, cities, dataset_metadata
```

- **Extract, load, then transform in SQL.** Raw rows go into a separate `staging` schema
  (created by a migration) with every column as text, exactly as downloaded; only the
  column names are normalized to snake_case. All the cleaning is in eight numbered,
  commented SQL files, which can be read top to bottom or run by hand. Parameters (the
  state, the reference year) come from a one-row `staging.params` table.
- **The app never reads `staging`.** The transform ends in two CSVs that are committed,
  so seeding (and Docker) need no network and no pipeline. The raw files stay out of git
  and out of the Docker image.
- **A changed source format fails loudly.** The loader checks every column the SQL
  needs before loading; a renamed CMS field stops the run instead of producing NULLs.

### Transform rules

| Rule | Choice (and file) |
|---|---|
| Specialty | An explicit mapping table from CMS primary specialty to our 10 slugs, each row commented: e.g. `CARDIOVASCULAR DISEASE (CARDIOLOGY)`, `INTERVENTIONAL CARDIOLOGY` → cardiology; family practice, internal medicine, general practice and geriatric medicine → primary care. Hospitalists, pediatrics, surgical oncology, critical care and other shared or inpatient-only fields are left out. Unmapped specialties are dropped and counted (`01_specialty_map.sql`) |
| One row per NPI | The NDF has a row per enrollment, group and address. Among the rows with a mapped specialty, pick: a ZIP that can be located, then the ZIP on the clinician's Medicare record, then the address listed most often, then the lowest address id (`05_select_address.sql`) |
| Credential | The NDF's if it is MD or DO; if blank, the Medicare file's ("M.D." → MD). Anything else is dropped: the schema only holds physicians |
| years_experience | Reference year − medical school graduation year; NULL if missing, in the future, or more than 60 years back. It counts residency too |
| patient_volume | Medicare beneficiaries seen in 2024 |
| cost_index | **Medicare spending per patient**: allowed amount for medical (non-drug) services per beneficiary (`Med_Mdcr_Alowd_Amt / Med_Tot_Benes`) ÷ the median of that for the specialty among the kept NJ providers who have it, so each specialty's median is exactly 1.0. Per patient, not per service: Medicare pays by fee schedule, so the amount per service mostly reflects which services are billed, not a price. Without Part B drugs, which mostly reflect the condition treated (`04_medicare_utilization.sql`). NULL (imputed) when CMS suppressed the medical amounts or fewer than 30 patients had medical services (`MIN_SPENDING_PATIENTS` in `app/services/dataset.py`, served by `GET /dataset`). Scored as a percentile within the specialty. Displayed as "Medicare spending per patient", never "cost" |
| quality_score | The MIPS final score (1–100). A clinician with several scores (individual, group, APM) gets the highest, as CMS does within a TIN. NULL without one, and NULL for a final score of 0, which means nothing that could be scored was submitted (CMS 2024 Traditional MIPS Scoring Guide; `03_mips_scores.sql`) |
| Location | The Census centroid of the practice ZIP |
| Not published | complication_rate, readmission_rate, accepting_new_patients, subspecialty, conditions: NULL / none |
| Search locations | NJ municipalities with 40,000+ residents, plus the largest in each county (65). The legal suffix is dropped ("Edison township" → "Edison"); a name another NJ municipality shares gets its county ("Washington (Gloucester County)") |

Every NPI in the NJ extract is either kept or dropped with exactly one reason, checked in
this order: specialty not mapped, no Medicare utilization record, not an MD or DO,
credential not published, missing name, no usable volume or spending, ZIP not located.
[data-quality.md](data-quality.md) has the counts, match rates between the datasets, and
distributions per specialty.

### Missing data in the app

Most clinicians have no MIPS score, so missing values are normal here. A missing quality
or experience is scored as the specialty median and flagged as imputed, which neither
rewards nor punishes a gap ([ranking.md](ranking.md#missing-values-real-data) explains
why). The imputation happens in the service layer (`services/imputation.py`, pure like the
engine), so the engine never sees a missing value. The API keeps the field `null` and
reports `imputed` / `not_reported` per metric, explanations never call an imputed value a
standout, and a minimum-quality or minimum-experience filter only matches real values.

`GET /dataset` describes the loaded data: source, label, release, available metrics,
whether conditions exist, and a disclaimer. For CMS data the disclaimer says it is real
public data, covers Medicare patients only, and that scores are illustrative, not a rating
or endorsement of any clinician. The seed records the dataset in `dataset_metadata`, and
the endpoint reads that rather than `DATA_SOURCE`, so the disclaimer can't go missing
because the app was started with a different `.env` than the seed. Searching with a
condition on CMS data returns `422 CONDITIONS_UNAVAILABLE`.

### Limitations

- **Medicare only.** Volume and spending come from Medicare Part B fee-for-service claims.
  Medicare Advantage, Medicaid and commercial patients aren't counted, so a pediatric or
  mostly-commercial practice looks small. Clinicians with fewer than 11 Medicare patients
  aren't in the file at all and are dropped.
- **Spending per patient isn't price, and isn't risk-adjusted.** It measures how much
  Medicare care a clinician bills for each patient they see, which also depends on how
  sick those patients are and what the practice does (a procedural cardiologist vs. a
  consult-only one). It is spread widely, so the ranking scores it as a percentile within
  the specialty: the fixed 0.5–1.5 scale used for synthetic data pinned a third of
  providers at 0 or 1. Part B drugs are left out (with them, oncology's 90th percentile
  was 9.6 times the median; without, 1.9), and about a fifth of providers have no usable
  figure (suppressed by CMS, or under 30 patients). An earlier version used allowed amount
  per service, which mostly measured the mix of services billed.
- **MIPS is a payment program score.** Its final score blends quality measures,
  improvement activities, interoperability and cost, and clinicians in advanced APMs or
  under the low-volume threshold don't get one. So coverage is partial and uneven by
  specialty, and a missing score says nothing about the clinician.
- **Vintages differ.** The NDF is current, while MIPS (PY 2024) and utilization
  (CY 2024) lag by one to two years. A clinician who moved or retired since may appear
  with old numbers.
- **Location is the ZIP centroid**, not the street address, so distances are
  approximate to within a ZIP code's size.

## 11. Directory tree

```
provideriq/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routes/        health.py reference.py providers.py search.py ai.py ranking.py
│   │   ├── core/              config.py errors.py logging.py middleware.py rate_limit.py
│   │   │                      request_context.py
│   │   ├── database/          base.py session.py
│   │   ├── models/            provider.py specialty.py condition.py city.py search_log.py
│   │   ├── schemas/           common.py provider.py search.py score.py reference.py
│   │   │                      ranking.py ai.py
│   │   ├── repositories/      provider_repository.py reference_repository.py search_log_repository.py
│   │   ├── services/
│   │   │   ├── search_service.py  geo.py  explanation.py
│   │   │   └── ranking/       normalization.py weights.py engine.py
│   │   └── ai/                base.py vocabulary.py criteria.py rule_based_parser.py
│   │                          llm_client.py llm_parser.py prompts.py factory.py crisis.py
│   ├── pipeline/              extract.py load.py transform.py data_quality.py sources.py
│   │                          sql/00_functions.sql … 07_cities.sql   (section 10)
│   ├── alembic/               env.py  versions/
│   ├── scripts/               generate_data.py seed_db.py app_db_role.py bench_search.py
│   │                          ranking_demo.py eval_parser.py
│   │                          smoke_test.py
│   ├── tests/                 conftest.py helpers.py  unit/  integration/
│   │                          fixtures/cms_raw/   (fake raw CMS/Census files)
│   ├── alembic.ini
│   ├── pyproject.toml         # ruff + pytest config
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── docker-entrypoint.sh   # migrate, seed if empty, serve
│   └── Dockerfile
├── frontend/
│   ├── src/                   (structure from section 4)
│   ├── tests/                 setup.ts utils.tsx fixtures.ts + *.test.ts(x)
│   ├── e2e/                   fixtures.ts mockApi.ts mobile.spec.ts links.spec.ts (Playwright)
│   ├── scripts/               screenshots.ts og-image.ts (Playwright)
│   ├── public/                favicon.svg og-image.png
│   ├── index.html
│   ├── vite.config.ts         # dev proxy + Vitest config
│   ├── tsconfig*.json         # app, node, test, e2e projects
│   ├── playwright.config.ts   # browser checks: vite preview + mocked API
│   ├── eslint.config.js
│   ├── .prettierrc.json
│   ├── .nvmrc                 # Node 24
│   ├── package.json
│   ├── nginx.conf             # SPA routing, /api/ proxy, security headers, caching
│   └── Dockerfile
├── data/
│   ├── reference/             cities.csv specialties.csv conditions.csv
│   ├── generated/             providers.csv provider_conditions.csv   (committed, seeded RNG)
│   ├── cms/                   providers_nj.csv cities_nj.csv MANIFEST.json   (committed)
│   └── raw/                   CMS and Census downloads   (gitignored)
├── db/init/                   01-create-test-db.sql   (runs on first volume init)
├── docs/                      architecture.md api.md ranking.md data-quality.md  screenshots/
├── .github/
│   ├── workflows/             backend.yml frontend.yml docker.yml
│   └── dependabot.yml
├── docker-compose.yml
├── .env.example               # copied to the repo-root .env
├── .gitignore
└── README.md
```
