# Connectivity Report

Date: 2026-06-13

Health endpoints

- `GET /health` — overall service health
- `GET /health/database` — database connectivity
- `GET /health/gemini` — Gemini/API connectivity and model validation
- `GET /health/config` — environment validation

Observed results on the patched backend

- Database: OK
- Gemini: OK
- Configuration: warning only when JWT auth is disabled and no secret key is configured
