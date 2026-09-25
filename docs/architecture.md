# ProviderIQ — Architecture

## 1. System architecture

```
                 ┌──────────────────────────────┐
  User ───────▶  │  React + TypeScript (Vite)   │
                 └──────────────┬───────────────┘
                                │ JSON over HTTP (/api/v1)
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
- **Explanations are template-based, not LLM-generated.** They're built from the score breakdown, e.g. *"Ranked mainly on quality (48.4 of 81.5 points), 15 years experience, 6.0 mi away."* That makes them free, instant, testable, and impossible to hallucinate. An LLM rewrite is a stretch goal.
- **Scores don't depend on who else matched.** Normalization uses fixed bounds or specialty-wide distributions, never min-max over the current result set. A provider's score is the same whether 5 or 500 others matched. This is what makes the detail page and the explanations consistent (see section 7).
- **Location lookup comes from a local `cities` table, not a geocoding API.** The synthetic providers are clustered around about 25 metro areas, and the user's location resolves against that same table. No external dependency, no API cost.
- **Dev workflow is Postgres in Docker, with backend and frontend run natively.** Faster reloads and easier debugging on Windows. Full `docker compose up` is the one-command demo and the CI path.

## 2. MVP feature set

**In:**

- Structured search: specialty, condition, location + radius, min quality, min experience, ranking priority
- Sorting, pagination, deterministic tie-breaking
- Ranking engine with a per-component score breakdown
- Natural-language parsing with an LLM, plus a rule-based fallback
- Provider detail page with metrics, conditions, score breakdown, and explanation
- Reference endpoints for the specialties and conditions dropdowns
- Synthetic data generator (about 1,500 providers) and seed script
- Search logging with no free text and no identifiers
- Consistent JSON errors, structured logging, CORS, body size limit, rate limiting
- Backend and frontend tests, Docker Compose, GitHub Actions CI
- AWS deployment
- Methodology page and a disclaimer on every page

**Out (post-MVP):**

- Elasticsearch, Redis, Airflow, dbt, Kubernetes
- User accounts and auth
- `POST /providers` — an admin write endpoint needs auth to be done properly, so data comes in through the seed script instead
- LLM-written explanations
- Maps UI

## 3. Backend structure

The layers are strict. Routes handle HTTP only. Services hold business logic. Repositories are the only code that touches SQLAlchemy. `ai/` never imports anything from `repositories/` or `database/`, and that separation is itself a security property.

```
backend/app/
├── main.py              # app factory: middleware, routers, error handlers
├── api/
│   ├── deps.py          # DB session, services, parser injection
│   └── routes/          # health, providers, reference, search, ai
├── core/                # config (pydantic-settings), errors, logging, middleware, rate_limit
├── database/            # engine/session, declarative Base
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response models
├── repositories/        # all queries live here
├── services/
│   ├── search_service.py   # orchestrates filter → distance → rank → paginate → log
│   ├── geo.py              # haversine + bounding box
│   ├── explanation.py      # templated explanations
│   └── ranking/            # normalization.py, weights.py, engine.py (pure functions)
└── ai/
    ├── base.py             # QueryParser protocol
    ├── llm_client.py       # provider-specific client behind an interface
    ├── llm_parser.py
    ├── rule_based_parser.py
    ├── prompts.py
    └── factory.py          # picks the parser from AI_PROVIDER env var
```

The ranking engine is pure Python: no database, no FastAPI. That makes it the easiest thing in the project to unit test exhaustively.

## 4. Frontend structure

```
frontend/src/
├── main.tsx, App.tsx          # router setup
├── pages/                     # SearchPage, ResultsPage, ProviderDetailPage, MethodologyPage, NotFoundPage
├── components/
│   ├── layout/                # AppLayout, Disclaimer
│   ├── search/                # NaturalLanguageSearch, CriteriaEditor
│   ├── results/               # ProviderCard, ResultsToolbar, Pagination
│   ├── provider/              # ScoreBreakdown, MetricGrid
│   └── common/                # LoadingState, ErrorState, EmptyState
├── services/                  # apiClient (fetch wrapper + error parsing), providersApi, searchApi, aiApi
├── hooks/                     # useSearch, useProvider, useReferenceData
├── types/                     # provider.ts, search.ts, api.ts
├── utils/                     # searchParams (URL ⇄ criteria), format
└── styles/                    # tokens.css (colors/spacing vars), global.css
```

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
providers            id PK, first_name, last_name, credential (MD/DO),
                     specialty_id FK → specialties, subspecialty (nullable text),
                     city, state, zip_code, latitude, longitude,
                     years_experience INT,
                     quality_score DOUBLE (0–100),
                     cost_index DOUBLE (1.00 = regional avg, lower = cheaper),
                     patient_volume INT (annual patients),
                     complication_rate DOUBLE (0–1), readmission_rate DOUBLE (0–1),
                     accepting_new_patients BOOL,
                     created_at, updated_at
provider_conditions  provider_id FK, condition_id FK   PK(provider_id, condition_id)
search_logs          id PK, created_at, source ('nl'|'manual'), parser_used,
                     specialty_id, state, priority, result_count, latency_ms
```

Why it's shaped this way:

- **Specialties get their own table.** They're a fixed vocabulary that feeds the dropdown. The foreign key prevents "Cardiology" vs "cardiology" drift, and the LLM's output gets validated against the same list.
- **Subspecialty stays as text.** It's sparse and only displayed, so a table would be over-normalizing.
- **Conditions need their own tables** because the relationship is many-to-many. There's no specialty column on conditions. "Which conditions go with cardiology" is derived by joining through the providers who treat them, so there's no extra table to keep in sync.
- **`cost_index` replaces `cost_score`.** "Cost score" is ambiguous: does high mean cheap or expensive? An index where 1.0 is average removes the ambiguity. Normalization turns it into cost efficiency.
- **`quality_score` is stored as a given rating.** It's generated to correlate with low complication and readmission rates, which are shown on the detail page. In a real system a data pipeline would compute this score from claims data (a natural hook for dbt later).
- **`search_logs` stores no query text and no condition.** People type their own health details into search boxes, so neither gets logged.

### Indexes

| Index | Why |
|---|---|
| `providers(specialty_id, state)` | Almost every search filters by specialty. The composite also covers specialty+state. |
| `providers(latitude, longitude)` | Supports the radius bounding-box prefilter. |
| `provider_conditions(condition_id)` | The primary key starts with `provider_id`, so "who treats X" needs the reverse direction. |
| `search_logs(created_at)` | Time-range queries for observability. |

No `quality_score` index: a minimum-quality filter usually matches most rows, so an index wouldn't help. At 1,500 rows Postgres will seq-scan regardless. We'll check with `EXPLAIN` and discuss when these indexes start to matter.

## 6. REST API (`/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | App and DB status |
| GET | `/specialties` | Dropdown data |
| GET | `/conditions?specialty=cardiology` | Conditions treated within a specialty |
| GET | `/providers?specialty=&state=&page=&page_size=` | Browse without ranking |
| GET | `/providers/{id}?priority=&city=&state=` | Detail; returns score + explanation when search context is passed |
| POST | `/search` | Ranked search with structured criteria |
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
  "provider": { "id": 412, "name": "Dr. ...", "specialty": "Cardiology", "...": "..." },
  "distance_miles": 6.0,
  "score": {
    "overall": 81.5,
    "components": [
      { "name": "quality", "raw": 88, "normalized": 0.88, "weight": 0.55, "contribution": 48.4 }
    ]
  }
}
```

Error format is always `{"error": {"code", "message", "details?"}}`:

| Code | Status |
|---|---|
| `VALIDATION_ERROR` | 422 |
| `LOCATION_NOT_FOUND` | 422 |
| `NOT_FOUND` | 404 |
| `PAYLOAD_TOO_LARGE` | 413 |
| `RATE_LIMITED` | 429 |
| `INTERNAL_ERROR` | 500 (no stack traces leaked) |

There's no "AI unavailable" error, because that case falls back instead of failing.

**Priority vs sort:** `priority` changes how the match score is computed. `sort` just picks the column to order by (match score, quality, experience, distance, or cost). They're kept separate on purpose so the UI isn't confusing.

## 7. Ranking system

**Step 1: normalize every component to [0, 1], where higher is better.**

| Component | Formula | Reasoning |
|---|---|---|
| Quality | `q = quality_score / 100` | Already on a fixed 0–100 scale. |
| Experience | `e = min(1, ln(1+years) / ln(31))` | Diminishing returns: 2→10 years matters more than 20→28. 5y → 0.52, 10y → 0.70, 20y → 0.89, 30y+ → 1.0 |
| Cost efficiency | `c = clamp(1.5 − cost_index, 0, 1)` | Maps an index range of 0.5–1.5 onto 1–0, so average cost (1.0) scores 0.5. |
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
4. Score, sort, and paginate.
5. Log the search.

Ranking the full filtered set in Python is fine at this scale. At 100M providers, scoring moves into the database or Elasticsearch.

## 8. How the AI parser connects to the backend

```
"cardiologist near NYC for heart failure, quality matters"
      │  POST /ai/parse-query   (max 500 chars, rate limited)
      ▼
QueryParser.parse(text) → ParseResult { criteria, parser_used, warnings }
      │
      ├─ LLMQueryParser
      │    • system prompt lists the ONLY allowed specialty/condition slugs + priorities
      │    • provider's structured-output / JSON-schema mode
      │    • 8s timeout, no tools, no DB access, no secrets in the prompt
      │    • response → Pydantic ParsedCriteria (extra="forbid", enums, bounded ranges)
      │    • post-validation: unknown slugs dropped with a warning, radius clamped 1–100,
      │      city checked against the cities table
      │
      └─ on timeout / API error / invalid output → RuleBasedQueryParser
           (synonym map like "heart doctor" → cardiology, city match,
            "within N miles" regex, priority keywords)
      ▼
Frontend shows editable criteria → user clicks Search → POST /search (structured only)
```

**Provider-agnostic design:** `LLMQueryParser` depends on an `LLMClient` interface with a single method, `complete_json(system, user, schema) -> dict`. Switching providers means writing one new client class and changing an env var. Tests use a `FakeLLMClient` that returns canned or malformed output, so tests never call a real API.

**Prompt injection:** the input is untrusted, and we assume someone will try "ignore instructions and...". The worst case is that the model outputs some other valid combination of enum values, which just means a different legitimate search. The LLM has no tools, no data access, and nothing secret to leak. Its output is validated against a closed schema and rendered as text (React escapes it). That's containing the blast radius instead of trying to detect every attack.

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

Backend tests get written inside each stage, not saved for the end.

**AWS plan (Stage 14, simplest credible setup):**

- The frontend is built to S3 and served through CloudFront.
- `/api/*` is routed by CloudFront to the FastAPI container on one EC2 instance, with RDS for Postgres.
- Everything sits on one HTTPS domain, so production needs no CORS.
- ECS Fargate plus an ALB is the "how I'd scale it" answer rather than a cost paid now.

## 10. Final directory tree

```
provideriq/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routes/        health.py providers.py reference.py search.py ai.py
│   │   ├── core/              config.py errors.py logging.py middleware.py rate_limit.py
│   │   ├── database/          base.py session.py
│   │   ├── models/            provider.py specialty.py condition.py city.py search_log.py
│   │   ├── schemas/           common.py provider.py search.py ai.py
│   │   ├── repositories/      provider_repository.py reference_repository.py search_log_repository.py
│   │   ├── services/
│   │   │   ├── search_service.py  geo.py  explanation.py
│   │   │   └── ranking/       normalization.py weights.py engine.py
│   │   └── ai/                base.py llm_client.py llm_parser.py rule_based_parser.py prompts.py factory.py
│   ├── alembic/               env.py  versions/
│   ├── scripts/               seed_db.py
│   ├── tests/                 conftest.py  unit/  integration/
│   ├── alembic.ini
│   ├── pyproject.toml         # ruff + pytest config
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── src/                   (structure from section 4)
│   ├── tests/                 setup.ts + *.test.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── eslint.config.js
│   ├── .prettierrc
│   ├── package.json
│   └── Dockerfile
├── data/
│   ├── generate_data.py
│   ├── reference/             cities.csv specialties.csv conditions.csv
│   └── generated/             providers.csv provider_conditions.csv   (committed, seeded RNG)
├── docs/                      architecture.md api.md ranking.md
├── .github/workflows/         backend.yml frontend.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```
