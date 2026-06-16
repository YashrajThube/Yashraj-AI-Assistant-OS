**UTC Migration Roadmap (high level)**

Goal: store datetimes in UTC canonically and make reads/writes timezone-safe.

Steps:
1. Audit current usage: locate all read/write sites for `events`, `notes`, and `failed_jobs` timestamps.
2. Backup DB and export all datetime columns (existing backups already created by repair scripts).
3. Add Alembic migration:
   - Add a maintenance migration that converts existing `DATETIME` values to UTC by interpreting current values as `APP_TIMEZONE` and writing UTC equivalents into new temporary columns (or overwrite after verification).
   - Option A (safer): add new columns `start_time_utc`, `end_time_utc`, populate them, switch app to use them, then drop old columns in a follow-up migration.
4. Update code paths: write all timestamps in UTC and set SQLAlchemy to expect UTC datetimes consistently.
5. Update tests, CI, and docs.
6. Run staged rollout with verification steps and rollback plan.

Rollback plan:
- Keep backups and a short window where both columns exist so the migration is reversible.

Estimated effort: medium (1-3 days depending on DB size and traffic), requires coordination for production migration window.