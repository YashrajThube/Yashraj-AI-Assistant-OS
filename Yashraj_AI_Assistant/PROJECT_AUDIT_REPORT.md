# Project Audit Report — Phase 1

Date: 2026-06-13

Summary
-------
- I scanned the repository and verified the backend and frontend run locally (tests: 26/26 passed, backend health OK, frontend dev server serving index).
- I created this Phase 1 audit that documents structure, duplicates, unused/docker files, risks, and recommended cleanup steps before larger refactors.

High-level structure
--------------------
- Top-level folders (workspace root): `backend/`, `logs/`, `Yashraj_AI_Assistant/`, `tests/` (top-level `backend` contains scripts/ reports)
- Primary application code is under `Yashraj_AI_Assistant/backend/` (this is the runnable backend used by tests and dev server).
- Frontend lives in `Yashraj_AI_Assistant/frontend/`.

Key findings
------------
1. Duplicate/back-to-back project roots
   - There are two `backend/` locations: one at repository root `backend/` (contains scripts and reports) and the main application under `Yashraj_AI_Assistant/backend/`.
   - This can be confusing. The running app and tests use `Yashraj_AI_Assistant/backend`.

2. Docker artifacts
   - Several docker-related files exist: `docker-compose.disabled.yml`, `.env.docker.example`, `.dockerignore`, `Dockerfile.disabled`, and I added `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, and `.env.example` earlier.
   - Phase 3 (per your plan) will remove Docker files entirely; keep in mind I already added working Dockerfiles/compose during initial checks — those will be removed in cleanup phase.

3. Secrets and credential files
   - `Yashraj_AI_Assistant/backend/credentials.json.json` exists. This likely contains OAuth client secrets — treat as sensitive and remove from repo. There may also be `token.json` files (check before removal).

4. Tests and dependencies
   - `Yashraj_AI_Assistant/requirements.txt` lists required packages; I installed them into the venv and ran tests successfully.
   - Tests passed (26 passed). The project uses `aiomysql` and `dateparser` among others; for local dev I used `sqlite+aiosqlite` to start the server without requiring MySQL.

5. Optional/experimental scripts and outputs
   - The repo contains many scripts and JSON outputs under `backend/scripts/` and top-level `backend/scripts/` (audit reports, backups, repair logs). Treat these as data artifacts; keep outside main package or move to `data/` if needed.

6. Frontend
   - Standard Vite + React app under `frontend/`. Dev server runs at `http://localhost:5173/`. Frontend static Dockerfile and nginx config exist.

Dependency map (high level)
---------------------------
- `app.py` (repo-root/backend/app.py) — entry that runs uvicorn pointing to `app.main:app`.
- `app/main.py` — assembles FastAPI app, imports routers from `app.api.*` and services from `app.services.*`; depends on `app.db.database` for engine and `app.core.config` for env.
- `app/core/config.py` — central env parsing; many required env vars are defined here.
- `app/db/database.py` — SQLAlchemy async engine and session factory; used by services and models.
- `app/api/*` — FastAPI route modules that import services and schemas.
- `app/services/*` — business logic; many depend on Google API clients, `dateparser`, and `ai_service`.
- `app/models/*` — SQLAlchemy models used by services and DB.
- `frontend/src/services/api.js` — client that calls backend API endpoints (checks this file to adapt base URL if needed).

Unused / Dead / Temporary files (candidates)
--------------------------------------------
- Top-level `backend/scripts/*.json` (reports/backups) — data artifacts, not source code.
- `Yashraj_AI_Assistant/backend/credentials.json.json` — likely secret; treat as sensitive.
- `*.disabled` Dockerfiles and compose files — disabled but present; Phase 3 will remove all Docker references.

Duplicates discovered
---------------------
- Multiple docker compose files: `docker-compose.disabled.yml`, `docker-compose.yml` (I added one).
- Dockerfiles: `backend/Dockerfile.disabled`, `backend/Dockerfile`, `frontend/Dockerfile.disabled`, `frontend/Dockerfile` (I added some).

Immediate risks and blockers
---------------------------
- Secrets committed: `credentials.json.json` (and possibly `token.json`). Remove immediately and rotate credentials if they are real.
- Two backend locations can confuse contributors and CI — plan to consolidate.

Recommendations (next steps)
---------------------------
1. Phase 1 sign-off: confirm you want Docker removed (Phase 3). I will delete all Docker-related files and references.
2. Move data artifacts (audit reports, backups) into a `data/` or `artifacts/` folder and add to `.gitignore` if not required.
3. Remove credentials and token files from repo history (use git rm and consider BFG or git-filter-repo if they contain real secrets).
4. Consolidate main application tree to `backend/` at repository root (or keep `Yashraj_AI_Assistant/backend` and remove root `backend/`), update paths and scripts accordingly. I recommend standardizing to `backend/` in repo root.
5. Create a formal `README.md`, `.env.example` (I added one), and Windows run scripts (`run_backend.ps1`, `run_frontend.ps1` already exist) with clear instructions.

Planned actions for Phase 2+ (summary)
--------------------------------------
- Remove duplicate/unused files and Docker artifacts.
- Refactor code where necessary for readability and maintainability (non-invasive, keep business logic).
- Ensure `requirements.txt` matches used imports; remove any unused dependencies.
- Run tests and verify backend and frontend start locally on Windows.

Files I changed/added during Phase 1
------------------------------------
- Added: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.env.example` (I will remove them in Phase 3 if you confirm removal of Docker).
- Added: `PROJECT_AUDIT_REPORT.md` (this file).

Concluding notes
----------------
This Phase 1 report maps the codebase and highlights the main cleanup steps. Confirm if you want me to proceed with Phase 2 (code cleanup) and Phase 3 (remove Docker). If yes, I will:

- Create a precise list of files to remove/relocate.
- Create backups where appropriate and run tests after each change.
- Remove secrets from the repository and produce `.env.example` with placeholders.
