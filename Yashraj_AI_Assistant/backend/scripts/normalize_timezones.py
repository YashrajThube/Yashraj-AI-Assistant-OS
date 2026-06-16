"""Normalize naive timestamps to APP_TIMEZONE (Asia/Kolkata) safely.

Rules:
 - Only convert naive datetimes (tzinfo is None)
 - Do NOT modify already timezone-aware timestamps
 - Preserve `google_event_id` and `sync_status`
 - Do NOT trigger any Google resync
 - Optionally normalize datetime-like fields in `failed_jobs.payload` for keys: scheduled_at, run_at, created_at

Usage:
  python normalize_timezones.py --apply
  python normalize_timezones.py (dry-run)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any
import runpy
import time

from sqlalchemy import text

from app.core.config import APP_TIMEZONE
from app.db.database import SessionLocal

logger = logging.getLogger("normalize_tz")
logging.basicConfig(level=logging.INFO)


def _is_naive(dt: Any) -> bool:
    return dt is not None and getattr(dt, "tzinfo", None) is None


def _tzify(dt: Any) -> Any:
    if dt is None:
        return None
    if _is_naive(dt):
        return dt.replace(tzinfo=ZoneInfo(APP_TIMEZONE))
    return dt


def _normalize_payload_timestamps(payload: str) -> tuple[str, list[str]]:
    """Parse JSON payload and normalize common timestamp keys if naive ISO strings found.

    Returns (new_payload_str, list_of_keys_normalized)
    """
    try:
        data = json.loads(payload)
    except Exception:
        return payload, []

    normalized_keys = []
    for key in ("scheduled_at", "run_at", "created_at"):
        if key in data and isinstance(data[key], str):
            s = data[key]
            # skip if contains timezone offset or Z
            if ("+" in s and ":" in s.split("+")[-1]) or s.endswith("Z") or s.endswith("z"):
                continue
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                continue
            if getattr(dt, "tzinfo", None) is None:
                data[key] = dt.replace(tzinfo=ZoneInfo(APP_TIMEZONE)).isoformat()
                normalized_keys.append(key)

    if not normalized_keys:
        return payload, []
    return json.dumps(data, ensure_ascii=False), normalized_keys


def _tz_ser(dt: Any) -> Any:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


async def normalize(apply: bool) -> dict:
    report = {"timestamp": datetime.now().isoformat(), "events_updated": [], "notes_updated": [], "failed_jobs_updated": [], "skipped": []}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"backend/scripts/normalize_timezones_backup_{ts}.json")
    log_path = Path("backend/scripts/normalize_timezones.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    to_backup: dict[str, list] = {"events": [], "notes": [], "failed_jobs": []}

    async with SessionLocal() as db:
        # Events: collect naive rows
        rows = await db.execute(text("SELECT id, start_time, end_time, google_event_id, sync_status FROM events"))
        ev = rows.fetchall()
        events_to_update = []
        for id_, start_time, end_time, google_event_id, sync_status in ev:
            if _is_naive(start_time) or _is_naive(end_time):
                to_backup["events"].append({"id": id_, "start_time": _tz_ser(start_time), "end_time": _tz_ser(end_time), "google_event_id": google_event_id, "sync_status": sync_status})
                events_to_update.append((id_, start_time, end_time, google_event_id, sync_status))

        # Notes: collect naive created_at
        nrows = await db.execute(text("SELECT id, created_at FROM notes"))
        notes_to_update = []
        for nid, created_at in nrows.fetchall():
            if _is_naive(created_at):
                to_backup["notes"].append({"id": nid, "created_at": _tz_ser(created_at)})
                notes_to_update.append((nid, created_at))

        # failed_jobs: collect payloads that would be modified
        fj = await db.execute(text("SELECT id, payload FROM failed_jobs"))
        failed_jobs_to_update = []
        for jid, payload in fj.fetchall():
            new_payload, keys = _normalize_payload_timestamps(payload)
            if keys:
                to_backup["failed_jobs"].append({"id": jid, "payload": payload})
                failed_jobs_to_update.append((jid, new_payload, keys))

        # write backup
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(to_backup, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Backup written: %s", backup_path)

        # Print before summary
        if events_to_update or notes_to_update or failed_jobs_to_update:
            print("Timezone normalization will affect the following rows (before -> after shown when applied):")
            for id_, s, e, geid, ss in events_to_update:
                print(f"event {id_}: start={_tz_ser(s)} end={_tz_ser(e)} google_event_id={geid} sync_status={ss}")
            for nid, c in notes_to_update:
                print(f"note {nid}: created_at={_tz_ser(c)}")
            for jid, newp, keys in failed_jobs_to_update:
                print(f"failed_job {jid}: payload_keys_normalized={keys}")
        else:
            print("No naive timestamps found; nothing to apply.")

        # Apply updates
        if apply and (events_to_update or notes_to_update or failed_jobs_to_update):
            for id_, s, e, geid, ss in events_to_update:
                ns = _tzify(s) if _is_naive(s) else s
                ne = _tzify(e) if _is_naive(e) else e
                await db.execute(text("UPDATE events SET start_time = :s, end_time = :e WHERE id = :id"), {"s": ns, "e": ne, "id": id_})
                report["events_updated"].append({"id": id_, "google_event_id": geid, "sync_status": ss, "before_start": _tz_ser(s), "before_end": _tz_ser(e), "after_start": _tz_ser(ns), "after_end": _tz_ser(ne)})

            for nid, c in notes_to_update:
                nc = _tzify(c)
                await db.execute(text("UPDATE notes SET created_at = :c WHERE id = :id"), {"c": nc, "id": nid})
                report["notes_updated"].append({"id": nid, "before": _tz_ser(c), "after": _tz_ser(nc)})

            for jid, newp, keys in failed_jobs_to_update:
                await db.execute(text("UPDATE failed_jobs SET payload = :p WHERE id = :id"), {"p": newp, "id": jid})
                report["failed_jobs_updated"].append({"id": jid, "normalized_keys": keys})

            await db.commit()

            # print after values for events
            print("Applied timezone normalization. Before -> After:")
            for ev in report["events_updated"]:
                print(f"event {ev['id']}: {ev['before_start']} -> {ev['after_start']}, {ev['before_end']} -> {ev['after_end']}")
            for n in report["notes_updated"]:
                print(f"note {n['id']}: {n['before']} -> {n['after']}")
        else:
            logger.info("No changes applied (dry-run or nothing to change)")

    # Write report
    out = Path("backend/scripts/normalize_timezones_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote timezone normalization report: %s", out)
    # If we applied changes, run DB audit and Google consistency check for affected events
    final = {"normalization_report": str(out), "db_audit_report": None, "google_consistency_report": None}
    if apply:
        try:
            # run db audit script (dry-run)
            runpy.run_path(str(Path(__file__).parent / 'db_integrity_audit.py'))
            final["db_audit_report"] = str(Path('backend/scripts/db_integrity_audit_report.json'))
        except Exception as exc:
            logger.exception("Failed to run DB audit: %s", exc)

        # Google consistency: check events we updated
        try:
            creds = None
            try:
                from app.services.google_auth_service import load_saved_credentials
                creds = await load_saved_credentials()
            except Exception:
                creds = None

            mismatches = []
            checked = 0
            if creds and report["events_updated"]:
                from googleapiclient.discovery import build
                from zoneinfo import ZoneInfo as _Z
                service = build('calendar','v3',credentials=creds,cache_discovery=False)
                for ev in report["events_updated"]:
                    checked += 1
                    geid = ev.get('google_event_id')
                    if not geid:
                        continue
                    try:
                        g = service.events().get(calendarId='primary', eventId=geid).execute()
                    except Exception as exc:
                        mismatches.append({'id': ev['id'], 'google_event_id': geid, 'error': str(exc)})
                        continue
                    gstart = g.get('start',{}).get('dateTime')
                    if not gstart:
                        continue
                    try:
                        g_dt = datetime.fromisoformat(gstart)
                    except Exception:
                        from dateutil import parser
                        g_dt = parser.isoparse(gstart)
                    # parse DB after value
                    db_dt = None
                    try:
                        db_dt = datetime.fromisoformat(ev['after_start']) if isinstance(ev['after_start'], str) else ev['after_start']
                    except Exception:
                        db_dt = None
                    if db_dt is not None:
                        db_utc = db_dt.astimezone(_Z('UTC'))
                        g_utc = g_dt.astimezone(_Z('UTC'))
                        diff = abs((db_utc - g_utc).total_seconds())
                        if diff > 60:
                            mismatches.append({'id': ev['id'], 'google_event_id': geid, 'db': ev['after_start'], 'google': g_dt.isoformat(), 'diff_seconds': diff})

            gcr = Path('backend/scripts/google_consistency_report.json')
            gcr.write_text(json.dumps({'mismatches': mismatches, 'checked': checked}, ensure_ascii=False, indent=2), encoding='utf-8')
            final['google_consistency_report'] = str(gcr)
        except Exception as exc:
            logger.exception("Google consistency check failed: %s", exc)

        # write final combined report
        final_path = Path('backend/scripts/normalize_timezones_final_report.json')
        final_path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info("Wrote final normalization report: %s", final_path)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply timezone normalization")
    args = ap.parse_args()
    asyncio.run(normalize(args.apply))


if __name__ == "__main__":
    main()
