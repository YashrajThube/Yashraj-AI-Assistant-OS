**Monitoring Recommendations**

Nightly checks (cron / CI job):
- Run `backend/scripts/db_integrity_audit.py` (dry-run) and raise alerts for new issues.
- Run `backend/scripts/google_consistency_report.json` check: verify key events remain consistent and no new mismatches introduced.
- Monitor `failed_jobs` table for growth or repeated `retrying`/`failed` statuses.

Alerting thresholds:
- Any new `implausible_year` or `start_after_end` issue → pager/alert.
- `failed_jobs` count > 10 or any job retry_count > 3 → notify.

Retention & logs:
- Keep `normalize_timezones_backup_*.json` and `repair_events_backup_*.json` for 30 days.
- Archive weekly audit reports to an S3 or central logging bucket.

Operational runbook:
- How to review a Google mismatch: open `backend/scripts/google_consistency_report.json`, inspect `id`, `db`, `google`, and follow the in-place update procedure only after manual approval.