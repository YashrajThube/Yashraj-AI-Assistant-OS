"""Database integrity audit and safe repairs for production readiness.

Usage:
  python db_integrity_audit.py --dry-run
  python db_integrity_audit.py --apply

This script performs scans across `events`, `notes`, and `failed_jobs`, detects issues,
produces a JSON report, and with `--apply` will perform safe normalizations and orphan cleanup.
Safe repairs implemented:
 - timezone normalization for datetime fields to APP_TIMEZONE
 - sync_status normalization for `events` to allowed set
 - orphaned `failed_jobs` referencing missing events are archived and deleted

Never deletes valid rows or overwrites existing `google_event_id` values.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import text

from app.core.config import APP_TIMEZONE
from app.db.database import SessionLocal

logger = logging.getLogger("db_audit")
logging.basicConfig(level=logging.INFO)


ALLOWED_SYNC_STATUS = {"pending", "synced", "retry_pending", "failed"}


def _tzify(dt: Any) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt)
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(APP_TIMEZONE))
    return dt.astimezone(ZoneInfo(APP_TIMEZONE))


async def run_audit(apply: bool) -> dict:
    report: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat(), "issues": [], "counts": {}, "repairs": [], "warnings": []}

    async with SessionLocal() as db:
        # Counts by sync_status
        rows = await db.execute(text("SELECT sync_status, COUNT(*) FROM events GROUP BY sync_status"))
        counts = {r[0]: int(r[1]) for r in rows.fetchall()}
        report["counts_by_sync_status"] = counts

        # Events scan
        ev_rows = await db.execute(text("SELECT id, title, start_time, end_time, google_event_id, sync_status FROM events"))
        events = ev_rows.fetchall()
        now = datetime.now(timezone.utc)
        malformed = []
        duplicates = []
        for row in events:
            eid, title, start_time, end_time, google_event_id, sync_status = row

            # check nulls
            if start_time is None or end_time is None:
                malformed.append({"id": eid, "issue": "null_timestamp"})
                continue

            # timezone normalization check
            if getattr(start_time, "tzinfo", None) is None or getattr(end_time, "tzinfo", None) is None:
                report["issues"].append({"id": eid, "issue": "naive_timestamp"})
                if apply:
                    ns = _tzify(start_time)
                    ne = _tzify(end_time)
                    await db.execute(text("UPDATE events SET start_time = :s, end_time = :e WHERE id = :id"), {"s": ns, "e": ne, "id": eid})
                    report["repairs"].append({"id": eid, "fix": "timezone_normalized"})

            # impossible years
            if start_time.year < 1970 or start_time.year > (now.year + 5) or end_time.year < 1970 or end_time.year > (now.year + 5):
                report["issues"].append({"id": eid, "issue": "implausible_year", "start": str(start_time), "end": str(end_time)})
                # shift years into plausible range if apply
                if apply:
                    # shift year preserving month/day/time
                    def _shift(dt):
                        if dt is None:
                            return None
                        y = min(max(dt.year, 1970), now.year + 5)
                        return dt.replace(year=y)

                    ns = _shift(start_time)
                    ne = _shift(end_time)
                    await db.execute(text("UPDATE events SET start_time = :s, end_time = :e WHERE id = :id"), {"s": ns, "e": ne, "id": eid})
                    report["repairs"].append({"id": eid, "fix": "implausible_year_shifted"})

            # start > end
            if start_time and end_time and start_time >= end_time:
                report["issues"].append({"id": eid, "issue": "start_after_end", "start": str(start_time), "end": str(end_time)})
                if apply:
                    # try to infer duration 1 hour
                    ne = start_time + timedelta(hours=1)
                    await db.execute(text("UPDATE events SET end_time = :e WHERE id = :id"), {"e": ne, "id": eid})
                    report["repairs"].append({"id": eid, "fix": "end_time_inferred_1h"})

            # sync_status normalization
            if sync_status not in ALLOWED_SYNC_STATUS:
                report["issues"].append({"id": eid, "issue": "invalid_sync_status", "value": sync_status})
                if apply:
                    await db.execute(text("UPDATE events SET sync_status='pending' WHERE id = :id"), {"id": eid})
                    report["repairs"].append({"id": eid, "fix": "sync_status_normalized_to_pending"})

        # duplicate detection: same title + start_time
        seen = {}
        for eid, title, start_time, end_time, google_event_id, sync_status in events:
            key = (title or "", getattr(start_time, "isoformat", lambda: str(start_time))())
            if key in seen:
                duplicates.append({"ids": [seen[key], eid], "title": title, "start": str(start_time)})
            else:
                seen[key] = eid

        report["duplicate_events"] = duplicates

        # Failed jobs scan
        fj = await db.execute(text("SELECT id, type, payload, retry_count, status FROM failed_jobs"))
        fj_rows = fj.fetchall()
        orphaned_jobs = []
        for jid, jtype, payload, retry_count, status in fj_rows:
            try:
                p = json.loads(payload)
            except Exception:
                report["issues"].append({"failed_job_id": jid, "issue": "invalid_payload"})
                continue

            if jtype == "google_sync":
                event_id = int(p.get("event_id") or 0)
                r = await db.execute(text("SELECT id FROM events WHERE id = :id"), {"id": event_id})
                if r.fetchone() is None:
                    report["issues"].append({"failed_job_id": jid, "issue": "orphaned_failed_job", "event_id": event_id})
                    orphaned_jobs.append(jid)

        if apply and orphaned_jobs:
            # backup orphaned jobs
            backup_path = Path("backend/scripts/failed_jobs_orphan_backup_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = Path("backend/scripts") / f"failed_jobs_orphan_backup_{ts}.json"
            rows = await db.execute(text("SELECT id, type, payload, retry_count, status FROM failed_jobs WHERE id IN :ids"), {"ids": tuple(orphaned_jobs)})
            data = [dict(zip(["id","type","payload","retry_count","status"], r)) for r in rows.fetchall()]
            backup_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            # delete orphaned jobs
            await db.execute(text("DELETE FROM failed_jobs WHERE id IN :ids"), {"ids": tuple(orphaned_jobs)})
            report["repairs"].append({"deleted_failed_jobs": orphaned_jobs, "backup": str(backup_file)})

        # Notes scan: timezone normalization for created_at
        nrows = await db.execute(text("SELECT id, created_at FROM notes"))
        for nid, created_at in nrows.fetchall():
            if created_at is None:
                report["issues"].append({"note_id": nid, "issue": "missing_created_at"})
                continue
            if getattr(created_at, "tzinfo", None) is None:
                report["issues"].append({"note_id": nid, "issue": "naive_created_at"})
                if apply:
                    nc = _tzify(created_at)
                    await db.execute(text("UPDATE notes SET created_at = :c WHERE id = :id"), {"c": nc, "id": nid})
                    report["repairs"].append({"note_id": nid, "fix": "created_at_tz_normalized"})

        # alembic_version check
        try:
            av = await db.execute(text("SELECT version_num FROM alembic_version"))
            ver = av.fetchone()
            report["alembic_version"] = ver[0] if ver else None
        except Exception:
            report["alembic_version"] = None

        # index health: list indexes for tables
        idx = {}
        for tbl in ("events", "notes", "failed_jobs"):
            res = await db.execute(text("SELECT INDEX_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"), {"tbl": tbl})
            idx[tbl] = [dict(zip(["index","column"], r)) for r in res.fetchall()]
        report["indexes"] = idx

        if apply:
            await db.commit()

    # Write report
    out_path = Path("backend/scripts/db_integrity_audit_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote DB audit report: %s", out_path)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply safe repairs")
    args = ap.parse_args()
    asyncio.run(run_audit(args.apply))


if __name__ == "__main__":
    main()
