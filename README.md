# ProviderIQ

AI-assisted healthcare provider discovery and ranking. Portfolio project.

> Educational project only. All provider data is synthetic. This is not a medical
> recommendation system and does not provide medical advice.

## Status

In development. Full documentation comes at the end of the build.

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
