**Docker & Compose Deployment (DISABLED)**

Docker-based workflows have been intentionally disabled in this repository to enforce a local, non-containerized development workflow. The original Compose and Dockerfiles have been preserved with a `.disabled` suffix in the repository root and respective service folders.

Local development (preferred):

- **Backend**: use `scripts/run_backend.ps1`
- **Frontend**: use `scripts/run_frontend.ps1`
- **Full system**: use `scripts/run_full_system.ps1` to open backend and frontend in separate PowerShell windows.

If you need to re-enable Docker for CI or production testing, rename `docker-compose.disabled.yml` to `docker-compose.yml` and rename `backend/Dockerfile.disabled` and `frontend/Dockerfile.disabled` back to `Dockerfile`.

Notes:
- The project preserves `backend/credentials.json`, `backend/token.json`, `.env`, migration scripts, and backups — these files must not be modified.
- Docker-related CI workflows (if present) have been left unchanged; maintainers can disable them in `.github/workflows/` as needed.

