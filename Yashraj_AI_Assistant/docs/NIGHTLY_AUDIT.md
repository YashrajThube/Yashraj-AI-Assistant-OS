**Nightly Audit Automation**

Purpose: run automated integrity checks every night and upload reports for review.

What runs:
- `backend/scripts/db_integrity_audit.py` (dry-run)
- `backend/scripts/normalize_timezones.py` (dry-run)
- `backend/scripts/google_consistency_report.json` generation (via script)

Where: configured in `.github/workflows/nightly_audit.yml` (runs at 02:00 UTC daily).

Artifacts: audit JSON reports are uploaded as GitHub Action artifacts for retention and review.