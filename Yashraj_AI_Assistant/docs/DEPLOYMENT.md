**Deployment Readiness**

This repository has been configured to run locally without Docker. Dockerfiles and Compose were preserved with a `.disabled` suffix. Use the `scripts/` helpers for local development; see `scripts/run_backend.ps1` and `scripts/run_frontend.ps1`.

Platform guidance (if deploying to a container platform):
- Ensure `DATABASE_URL`, `GOOGLE_CLIENT_SECRETS_FILE`, and `GOOGLE_TOKEN_FILE` are provided securely via platform secrets.
- Ensure HTTPS via platform-managed TLS.

Environment variables (minimum):
- `DATABASE_URL`, `APP_TIMEZONE=Asia/Kolkata`, `GOOGLE_CLIENT_SECRETS_FILE`, `GOOGLE_TOKEN_FILE`, `API_HOST`, `API_PORT`.

Backups & strategy:
- Daily DB dump; keep last 30 days incremental.
- Keep `backend/scripts/*backup*.json` artifacts; upload to long-term storage.
