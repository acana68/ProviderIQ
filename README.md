# ProviderIQ

[![Backend](https://github.com/acana68/ProviderIQ/actions/workflows/backend.yml/badge.svg)](https://github.com/acana68/ProviderIQ/actions/workflows/backend.yml)
[![Frontend](https://github.com/acana68/ProviderIQ/actions/workflows/frontend.yml/badge.svg)](https://github.com/acana68/ProviderIQ/actions/workflows/frontend.yml)
[![Docker](https://github.com/acana68/ProviderIQ/actions/workflows/docker.yml/badge.svg)](https://github.com/acana68/ProviderIQ/actions/workflows/docker.yml)

AI-assisted healthcare provider discovery and ranking. Portfolio project.

> Educational project only. All provider data is synthetic. This is not a medical
> recommendation system and does not provide medical advice.

## Status

In development. Full documentation comes at the end of the build.

## Run everything with Docker

Needs Docker with Compose v2. From the repo root:

    cp .env.example .env        # then set POSTGRES_PASSWORD (URL-safe: no @ : / ? #)
    docker compose up --build

Open http://localhost:8080. The first start migrates the database and loads the synthetic
data (`SEED_IF_EMPTY`); later starts keep whatever is there. `.env` is read at runtime and
never copied into an image.

| Port | Service | Notes |
|---|---|---|
| 8080 | frontend (nginx) | The app. Proxies `/api/` to the backend, so it's one origin |
| 8000 | backend (FastAPI) | Direct API access; docs at http://localhost:8000/docs |
| 5433 | db (Postgres 17) | Host port for local tools and tests; `db:5432` inside Compose |

Stop the local dev servers first if they're running: the backend container also wants port
8000.

Check a running stack end to end (standard library only, no virtualenv needed):

    python backend/scripts/smoke_test.py            # defaults to http://localhost:8080

**Reseed** (replaces all provider data with `data/`; refused when `ENVIRONMENT=prod`):

    docker compose exec backend python -m scripts.seed_db

**Start from scratch** (deletes the database volume, including the test database; the next
`up` recreates and reseeds it):

    docker compose down -v
    docker compose up --build

The containers share the `provideriq-pgdata` volume with the local setup below, so both see
the same data. For development, `npm run dev` (http://localhost:5173, hot reload) with a
local uvicorn is still the faster loop; `docker compose up -d db` starts only the database.

## Continuous integration

Every push to `main` and every pull request runs three GitHub Actions workflows:

- **Backend**: ruff lint and format, then pytest against a Postgres 17 service container
  (live AI tests stay deselected; `AI_PROVIDER=none`).
- **Frontend**: typecheck, lint, format check, tests and build, on the Node version in
  `frontend/.nvmrc`.
- **Docker**: builds and starts the whole Compose stack, waits for it to be healthy, and
  runs the smoke test against http://localhost:8080.

Dependabot proposes weekly updates for pip, npm, GitHub Actions and the Docker base images.

## Backend (local)

    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements-dev.txt
    uvicorn app.main:app --reload

API docs: http://localhost:8000/docs

## Frontend (local)

Requires Node 24 (see `frontend/.nvmrc`). Start the backend first: the dev server
proxies `/api` to http://localhost:8000.

    cd frontend
    npm install
    npm run dev            # http://localhost:5173

Other scripts:

    npm run typecheck      # tsc, strict mode
    npm run lint           # ESLint
    npm run format         # Prettier (format:check to verify only)
    npm test               # Vitest, once (test:watch to keep running)
    npm run build          # type-check and build to dist/
    npm run preview        # serve dist/, with the same /api proxy
