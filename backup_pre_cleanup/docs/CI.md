**CI Pipeline**

Tasks executed in CI (GitHub Actions):
- Install dependencies (`requirements.txt`).
- Run `pytest` (tests under `tests/`).
- Run formatting check (`black --check`).
- Run linters (`flake8`).
- Run `backend/scripts/db_integrity_audit.py` (dry-run) to ensure no data anomalies.

Files added:
- `.github/workflows/ci.yml` — runs on push/PR.
- `.github/workflows/nightly_audit.yml` — scheduled daily audit.

Notes:
- CI is non-destructive and uses project tests and audit scripts to fail fast on regressions.