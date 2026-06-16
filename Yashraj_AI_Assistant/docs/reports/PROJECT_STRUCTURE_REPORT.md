# Project Structure Report

Date: 2026-06-13

Current high-level structure (key folders)

- `backend/` — Primary FastAPI backend application (entry: `backend/app.py`, module: `app.*`).
- `frontend/` — Vite + React frontend (dev: `npm run dev`, build: `npm run build`).
- `tests/` — PyTest tests (26 tests passing).
- `docs/` — Documentation and `docs/reports/` for generated reports.
- `data/artifacts/` — Archived audit and repair JSON artifacts moved here (ignored by Git).

Notes on consolidation
- Removed duplicate top-level `backend/` (which only contained script outputs) and consolidated the application under `backend/` inside the repository root.

Files moved
- `../backend/scripts/*.json` -> `data/artifacts/` (moved archive artifacts into project data folder)
