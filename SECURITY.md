# Security

ProviderIQ is an educational portfolio project: a public, read-only provider search. It has
no user accounts and stores no personal data about its users. By default the providers are
synthetic. An optional dataset uses public CMS data about real clinicians (see
[the CMS data](#the-cms-data)).

This page lists the security measures that exist in the code today, what is deliberately
out of scope, the known limitations, and how to report a problem.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting: the repository's **Security** tab →
**Report a vulnerability**. Don't open a public issue for anything exploitable. Include
what you found, how to reproduce it, and what it affects. Only the `main` branch is
supported.

## What's in place

### Secrets

- `.env` is git-ignored, and every Docker build context excludes `**/.env` and `**/.env.*`
  (`.dockerignore`, `frontend/.dockerignore`), so secrets never reach an image layer. They
  are passed to containers at runtime.
- Each container gets only the secrets it uses. The `db` container receives just
  `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`, not the whole `.env` (so no API
  key). The backend's entrypoint uses the owner's database credentials for migrations and
  seeding, then unsets them (`MIGRATION_DATABASE_URL`, `POSTGRES_PASSWORD`,
  `TEST_DATABASE_URL`) before starting the API process.
- The runtime role's password is hashed (SCRAM-SHA-256) on the client before it's sent to
  Postgres (`backend/scripts/app_db_role.py`), so the server and its logs never see it in
  plain text.
- The Anthropic API key is a pydantic `SecretStr` (`backend/app/core/config.py`): it never
  appears in reprs, logs or error messages. A blank value means "no key".
- CI uses no secrets at all: the AI parser is off (`AI_PROVIDER: none`), the live API tests
  are deselected, and the CI database password is a throwaway for a one-job container.
- **Secret scanning.** `.github/workflows/secrets.yml` runs gitleaks over the whole Git
  history on every push and pull request, with findings redacted in the log. The full
  history was scanned when this was added and was clean.

### Input validation

- Every request body is a closed Pydantic schema (`extra="forbid"`) with bounded values:
  radius 1–100 miles, `page_size` ≤ 50 (search) or ≤ 100 (browse), provider ids within
  Postgres's 32-bit range, natural-language queries ≤ 500 characters, slugs ≤ 100
  characters and required to name a known specialty or condition (422 otherwise), state
  codes checked by pattern (`backend/app/schemas/`).
- Validation errors name the field and the rule, never the submitted value.
- Database `CHECK` constraints back the schemas (`backend/app/models/`).
- The frontend parses URL state strictly and drops anything malformed or out of range
  (`frontend/src/utils/searchParams.ts`). The "Back to results" link only follows
  `/results` paths, so it can't become an open redirect.

### Parameterized queries

- All app SQL goes through SQLAlchemy with bound parameters; no request value is ever
  formatted into SQL.
- The CMS pipeline builds identifiers with psycopg's `sql.Identifier` and loads raw files
  with `COPY` into text columns (`backend/pipeline/load.py`). Its SQL files take their
  parameters from a table, not string formatting.

### Database roles

The API can't change what it serves, even if it were compromised:

- **Owner role** (`POSTGRES_USER`, `MIGRATION_DATABASE_URL`): runs Alembic, seeding and
  the CMS pipeline, and owns every table.
- **Runtime role** `provideriq_app` (`DATABASE_URL`): what the API connects as. It has
  `SELECT` on the app's tables, `INSERT` on `search_logs` (and its id sequence), and
  nothing else: no `UPDATE`, `DELETE` or `TRUNCATE`, no DDL, no access to the pipeline's
  `staging` schema, and none of superuser, `CREATEROLE`, `CREATEDB` or `BYPASSRLS`.
- A migration (`backend/alembic/versions/2026_09_28-e5f1a2b7c9d4_runtime_role.py`) creates
  the role and its grants, and explicitly revokes `CREATE` on `public` from `PUBLIC`.
  Tables added later get no grant until a migration adds one.
- `backend/tests/integration/test_db_roles.py` checks the role's exact privileges on every
  table, that writes and DDL are refused, and that a whole search works with only its grants.

### Rate limits and request size

- A sliding-window rate limit per client IP: 120 requests a minute on the whole API, plus
  10 a minute on `POST /ai/parse-query` (429 with `Retry-After`;
  `backend/app/core/rate_limit.py`). `/health/live` is exempt; `/health/ready` runs a query,
  so it's limited like everything else.
- The limiter keys on the socket peer address. uvicorn replaces that with the
  `X-Forwarded-For` address only on requests from `FORWARDED_ALLOW_IPS`
  (`backend/docker-entrypoint.sh`; the default, `127.0.0.1`, trusts no other host). Compose
  gives nginx a fixed address on its network (`172.29.53.10`) and trusts only that. nginx
  appends its peer's address to `X-Forwarded-For`, and uvicorn takes the rightmost untrusted
  entry, so it always gets the address nginx saw, never one the client wrote into the
  header. Each client therefore has its own bucket, and forging the header changes nothing
  (`backend/tests/unit/test_proxy_headers.py`).
- nginx also limits each address to 10 requests a second, with bursts of 20
  (`frontend/nginx.conf`), so a flood is shed before it reaches the backend. Its 429 uses
  the API's error shape.
- Request bodies over 64 KiB are rejected with 413, before reading them when
  `Content-Length` is present and while reading them when it isn't
  (`backend/app/core/middleware.py`).
- The AI call has an 8-second timeout and no retries.

### Security headers and CSP

nginx (`frontend/nginx.conf`) sets on every response:

- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`.
  The app loads nothing from other origins and has no inline scripts or styles.
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and `server_tokens off`.

The API also sets `X-Content-Type-Options: nosniff` and an `X-Request-ID` on every
response. CORS is an allow-list (`CORS_ORIGINS`), `GET` and `POST` only, without
credentials. The deployed shape is same-origin anyway, since nginx proxies `/api/`.

### Errors

Every error has the same JSON shape. Unexpected errors return a generic 500
`INTERNAL_ERROR` with a request ID; the traceback is only logged server-side.

### Containers

- The backend runs as an unprivileged `app` user. Its code is owned by root and read-only to
  that user, and the image holds runtime dependencies only (no test or build tools).
- The frontend is served by `nginxinc/nginx-unprivileged` on port 8080, as a non-root user.
- Compose publishes Postgres (5433) and the backend's direct port (8000) on `127.0.0.1`
  only, so they're reachable from this machine but not from the network. Only the app on
  8080 listens on all interfaces.
- Reseeding, which deletes all provider data, is refused when `ENVIRONMENT=prod`.
- With `ENVIRONMENT=prod`, `/docs`, `/redoc` and `/openapi.json` aren't served (404).
- Health checks are split: `/health/live` (liveness, touches nothing) and `/health/ready`
  (readiness, pings the database; 503 when it's down). Both are public, so neither reveals
  the app's version or environment.

### CI and dependencies

- Every workflow runs with `permissions: contents: read` and uses no secrets or tokens.
- `.github/workflows/audit.yml` runs `pip-audit` on the backend requirements (failing on
  any known vulnerability) and `npm audit --audit-level=high` on the frontend lockfile, on
  every push and pull request and weekly.
- **Pinned, not floating.** Every GitHub Action is pinned to a full commit SHA with its
  version in a comment (`actions/checkout@3d3c42e… # v7.0.1`). Every base image (Python,
  Node, nginx, and Postgres in Compose and CI) is pinned as `tag@sha256:digest`, with the
  exact version in a comment. A moved tag or a compromised release can't change what CI
  runs or what gets built.
- Dependabot proposes weekly updates for pip, npm, GitHub Actions (SHA and comment), and
  the Dockerfiles' and Compose file's images (digest and tag). Major versions that need a
  deliberate upgrade are ignored, each with the reason in `.github/dependabot.yml`: Python,
  Node, `@types/node` (tracks the Node in `.nvmrc`), TypeScript (until typescript-eslint
  supports 7) and Postgres (a new major needs a dump and restore).
- gitleaks runs from its official image pinned by digest, not a third-party action.

### AI containment

The language model has one narrow job and no power (`backend/app/ai/`):

- It only turns the user's sentence into search filters. It never ranks, never sees
  provider data and has no tools or database access. The filters are shown to the user
  for editing, and nothing is searched until they press Search.
- The query is HTML-escaped inside `<query>` tags, and the system prompt tells the model to
  treat it as data, not instructions.
- The output must match a closed schema. Every specialty, condition and city must then
  exist in the directory's vocabulary. Anything else is dropped, with a warning that
  doesn't repeat the rejected value.
- Any failure (timeout, API error, invalid output) falls back to the keyword parser, so a
  hostile or broken response can't do more than produce no filters.

### No query or health data in logs

People describe their own health in the search box, so:

- The query text is never logged or stored. `parse_query` logs only its length, the parser
  used, the latency and the number of warnings. AI failures log the exception type only.
- `search_logs` has no free-text or condition column: only source, parser, specialty,
  state, priority, result count and latency.
- The access log records method, path, status and duration: never the query string or
  client IP. Uvicorn's own access log (which includes query strings) is turned off.
- nginx's access log is set to the same fields (`frontend/nginx.conf`): no client address,
  query string (search criteria end up in `/results?...` URLs), referrer or user agent.
  Its error log can still include a client address, e.g. for a request `limit_req` rejected.
- The crisis flag (a query suggesting self-harm risk) is never logged or stored either.
- `/privacy` in the app explains all of this in plain language, without claiming
  compliance with any particular law.

### The CMS data

The optional real dataset contains only public CMS data about clinicians, never patients.
Whenever it's loaded:

- A banner on every page shows the dataset's disclaimer, its source and date. It says the
  data is real, covers Medicare patients only, and that scores are illustrative, not a
  rating or endorsement of any clinician.
- `GET /api/v1/dataset` returns the same disclaimer.
- The README screenshots are synthetic, and `npm run screenshots` refuses to run against
  real data.
- The pipeline checks every cached raw download against the SHA-256 recorded in
  `data/cms/MANIFEST.json` when it was downloaded: `pipeline.extract` before keeping a
  cached file, and `pipeline.transform` before loading any. A file that was edited,
  truncated or swapped stops the run, with the `--refresh` command that downloads it again.

## Out of scope, by design

- **Authentication and user data.** There are no accounts, sessions, cookies or user
  records to protect. Everything served is public, and the API is read-only apart from
  anonymous search counts.
- **TLS and HSTS.** The Docker stack serves plain HTTP on localhost. A real deployment
  belongs behind a TLS-terminating proxy, which should also set
  `Strict-Transport-Security`.
- **Distributed rate limiting.** Limits are counted in memory, per process. Several
  instances would each count separately.
- **Medical advice.** ProviderIQ isn't a medical device or a recommendation system.

## Known limitations

- **The costliest search is slow enough to matter.** A search with no filters ranks every
  provider in Python. Measured in-process in the backend container
  (`python -m scripts.bench_search`, 300 requests): p50 540 ms and p95 607 ms on the 9,071
  CMS providers; p50 69 ms and p95 119 ms on the 1,500 synthetic ones. At the 120-a-minute
  limit, one client can keep about one CPU core busy with CMS data loaded. Not optimized
  yet.
- **A proxy in front of nginx needs configuring.** The client address is the one nginx
  sees. Behind a load balancer that's the balancer, for every client, until nginx trusts it
  (`set_real_ip_from`, `real_ip_header`) or its address is added to `FORWARDED_ALLOW_IPS`.
- **Locally, all host clients share one address.** Docker Desktop forwards published ports
  from the host through its own gateway, so every browser on the host reaches nginx from
  the same address, and shares nginx's and the backend's per-address limits. Clients on
  the Compose network, or behind a real deployment's proxy, each get their own.
- **Some pins aren't updated automatically.** Dependabot doesn't update the Postgres image
  in `.github/workflows/backend.yml` (a service container) or the gitleaks image in
  `.github/workflows/secrets.yml` (a `docker run` command). Bump them by hand, the first
  together with `docker-compose.yml`'s. The `# syntax=docker/dockerfile:1` BuildKit
  frontends aren't pinned.
- nginx's own 429 has no `Retry-After` header; the backend's does.
- The Compose network uses the fixed subnet `172.29.53.0/24` so that nginx's address is
  known. If it clashes with a network on the host, change it together with `x-nginx-ip`.
