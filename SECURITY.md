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

### Rate limits and request size

- A sliding-window rate limit per client IP: 120 requests a minute on the whole API, plus
  10 a minute on `POST /ai/parse-query` (429 with `Retry-After`;
  `backend/app/core/rate_limit.py`). `/health` is exempt.
- The limiter keys on the socket peer address and ignores `X-Forwarded-For` unless uvicorn
  is told to trust the proxy (`FORWARDED_ALLOW_IPS`, `backend/docker-entrypoint.sh`), so a
  client can't forge a header to dodge it. See the known limitation below.
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
- Reseeding, which deletes all provider data, is refused when `ENVIRONMENT=prod`.

### CI and dependencies

- Every workflow runs with `permissions: contents: read` and uses no secrets or tokens.
- `.github/workflows/audit.yml` runs `pip-audit` on the backend requirements (failing on
  any known vulnerability) and `npm audit --audit-level=high` on the frontend lockfile, on
  every push and pull request and weekly.
- Dependabot proposes weekly updates for pip, npm, GitHub Actions and Docker base images.
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

### The CMS data

The optional real dataset contains only public CMS data about clinicians, never patients.
Whenever it's loaded:

- A banner on every page shows the dataset's disclaimer, its source and date. It says the
  data is real, covers Medicare patients only, and that scores are illustrative, not a
  rating or endorsement of any clinician.
- `GET /api/v1/dataset` returns the same disclaimer.
- The README screenshots are synthetic, and `npm run screenshots` refuses to run against
  real data.

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

- **Behind the bundled nginx, all clients share one rate-limit bucket.** In
  `docker-compose.yml`, requests reach the backend from the nginx container, and
  `FORWARDED_ALLOW_IPS` defaults to `127.0.0.1`, so the backend sees nginx's address for
  every client. The limits then apply to everyone combined: one busy client can use up the
  120-a-minute limit (or the AI's 10) for all. A deployment must set
  `FORWARDED_ALLOW_IPS` to its proxy's address.
- The Compose file publishes Postgres (5433) and the backend (8000) on all host
  interfaces, for local development. Don't run it on a shared network with the example
  password.
