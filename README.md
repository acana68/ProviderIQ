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
