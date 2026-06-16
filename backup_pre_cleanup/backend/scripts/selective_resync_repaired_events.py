"""Selective resync for repaired events.

Usage:
  python selective_resync_repaired_events.py --dry-run
  python selective_resync_repaired_events.py --apply

The script will:
 - Load the latest repair backup and applied files (or accept explicit paths)
 - Analyze repaired events individually against DB and Google Calendar
 - Produce a dry-run report listing candidates, duplicate risks, and reasons
 - With --apply, mark safe candidates as `retry_pending` and call POST /api/admin/sync_pending
 - Produce a final integrity report
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.google_auth_service import load_saved_credentials

logger = logging.getLogger("selective_resync")
logging.basicConfig(level=logging.INFO)


def _find_latest_applied_script(base_dir: Path) -> tuple[Path, Path] | None:
    scripts_dir = base_dir
    backups = sorted(scripts_dir.glob("repair_events_backup_*.json"))
    applied = sorted(scripts_dir.glob("repair_events_applied_*.json"))
    if not backups or not applied:
        return None
    # Match by timestamp suffix where possible
    # If multiple, prefer latest by mtime
    return backups[-1], applied[-1]


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def build_google_service(credentials) -> Any:
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError("googleapiclient not available: install google-api-python-client") from exc

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


async def check_google_event_exists(credentials, google_event_id: str) -> tuple[bool, dict | None]:
    if not google_event_id:
        return False, None
    loop = asyncio.get_running_loop()
    try:
        service = await loop.run_in_executor(None, build_google_service, credentials)
        def get_event():
            return service.events().get(calendarId="primary", eventId=google_event_id).execute()

        result = await loop.run_in_executor(None, get_event)
        return True, result
    except Exception:
        return False, None


async def search_google_events(credentials, title: str, start: datetime, end: datetime) -> list[dict]:
    loop = asyncio.get_running_loop()
    try:
        service = await loop.run_in_executor(None, build_google_service, credentials)

        time_min = (start - timedelta(minutes=1)).isoformat()
        time_max = (end + timedelta(minutes=1)).isoformat()

        def list_events():
            return (
                service.events()
                .list(calendarId="primary", timeMin=time_min, timeMax=time_max, q=title, singleEvents=True)
                .execute()
            )

        resp = await loop.run_in_executor(None, list_events)
        return resp.get("items", [])
    except Exception:
        return []


async def analyze_and_maybe_apply(backup_path: Path, applied_path: Path, apply: bool, base_url: str):
    with backup_path.open("r", encoding="utf-8") as f:
        before = json.load(f)
    with applied_path.open("r", encoding="utf-8") as f:
        after = json.load(f)

    # Map by id
    before_map = {b["id"]: b for b in before}
    after_map = {a["id"]: a for a in after}

    credentials = await load_saved_credentials()
    if credentials is None:
        logger.warning("No Google credentials available; will only produce dry-run data about DB state.")

    candidates = []
    skipped = []
    duplicate_risks = []
    to_mark_ids = []

    async with SessionLocal() as db:
        for eid, a in after_map.items():
            b = before_map.get(eid)
            r = await db.execute(text("SELECT id, title, start_time, end_time, google_event_id, sync_status FROM events WHERE id = :id"), {"id": eid})
            row = r.fetchone()
            if row is None:
                logger.warning("Event id %s not found in DB; skipping", eid)
                skipped.append({"id": eid, "reason": "missing_in_db"})
                continue

            (id_, title, start_time, end_time, google_event_id, sync_status) = row

            changed_integrity = False
            if b:
                # Compare old vs new start/end
                old_start = b.get("start_time")
                old_end = b.get("end_time")
                new_start = a.get("new_start") or a.get("start_time")
                new_end = a.get("new_end") or a.get("end_time")
                if old_start != new_start or old_end != new_end:
                    changed_integrity = True

            google_present = bool(google_event_id)
            candidate_reason = []

            if google_present and sync_status == "synced":
                skipped.append({"id": eid, "reason": "already_synced", "google_event_id": google_event_id})
                continue

            # If google_event_id present, check it exists
            google_exists = False
            google_event = None
            if credentials and google_event_id:
                google_exists, google_event = await check_google_event_exists(credentials, google_event_id)

            if google_present and google_exists:
                # Event exists in Google; check if integrity changed (e.g., start_time differs)
                g_start = google_event.get("start", {}).get("dateTime")
                if g_start and g_start != _iso(start_time):
                    candidate_reason.append("google_mismatch")
                else:
                    skipped.append({"id": eid, "reason": "google_exists_matching"})
                    continue

            # If no google_event_id or google missing, search nearby events by title+time to detect duplicates
            duplicate_found = False
            duplicate_details = None
            if credentials:
                found = await search_google_events(credentials, title or "", start_time, end_time)
                for item in found:
                    # compare title and start
                    gi = item.get("id")
                    gsum = item.get("summary")
                    gstart = item.get("start", {}).get("dateTime")
                    if gsum == (title or "") and gstart == _iso(start_time):
                        duplicate_found = True
                        duplicate_details = {"google_event_id": gi, "summary": gsum, "start": gstart}
                        break

            if duplicate_found:
                duplicate_risks.append({"id": eid, "duplicate": duplicate_details})
                skipped.append({"id": eid, "reason": "duplicate_risk", "details": duplicate_details})
                continue

            # Now determine if we should mark retry_pending
            if (not google_present) or (sync_status == "failed") or changed_integrity or (google_present and not google_exists):
                candidates.append({
                    "id": eid,
                    "sync_status": sync_status,
                    "google_event_id": google_event_id,
                    "changed_integrity": changed_integrity,
                })
                to_mark_ids.append(eid)
            else:
                skipped.append({"id": eid, "reason": "no_action_needed"})

        # Produce dry-run report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_repaired": len(after_map),
            "candidates": candidates,
            "skipped": skipped,
            "duplicate_risks": duplicate_risks,
        }

        report_path = applied_path.parent / "selective_resync_report_dryrun.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Dry-run report written: %s", report_path)

        if not apply:
            return report

        # Apply: mark safe candidates as retry_pending
        applied_ids = []
        for eid in to_mark_ids:
            # Double-check duplicate risk not present
            if any(d["id"] == eid for d in duplicate_risks):
                logger.warning("Skipping %s due to duplicate risk", eid)
                continue
            await db.execute(text("UPDATE events SET sync_status='retry_pending', sync_error='Selective resync requested' WHERE id = :id"), {"id": eid})
            applied_ids.append(eid)

        await db.commit()

    # Trigger admin sync endpoint to process retries
    import requests

    if applied_ids:
        logger.info("Marked events as retry_pending: %s", applied_ids)
        try:
            resp = requests.post(f"{base_url.rstrip('/')}/api/admin/sync_pending")
            logger.info("Called admin sync endpoint, status=%s", resp.status_code)
        except Exception as exc:
            logger.error("Failed to call admin sync endpoint: %s", exc)

    # Verification: re-query DB + Google
    final_report = {"timestamp": datetime.utcnow().isoformat(), "repaired_total": len(after_map), "re_synced": [], "skipped": skipped, "duplicate_risks": duplicate_risks}
    credentials = await load_saved_credentials()
    async with SessionLocal() as db:
        for eid in applied_ids:
            r = await db.execute(text("SELECT id, google_event_id, sync_status FROM events WHERE id = :id"), {"id": eid})
            row = r.fetchone()
            g_exists = False
            details = {"id": eid, "db_row": row and dict(zip(["id","google_event_id","sync_status"], row))}
            if credentials and row and row[1]:
                g_exists, ge = await check_google_event_exists(credentials, row[1])
                details["google_exists"] = g_exists
                details["google_event"] = ge
            final_report["re_synced"].append(details)

    final_path = applied_path.parent / "selective_resync_report_final.json"
    final_path.write_text(json.dumps(final_report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Final sync report written: %s", final_path)
    return final_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply selective retry markings after dry-run analysis")
    ap.add_argument("--backup", type=str, help="Path to repair_events_backup_*.json")
    ap.add_argument("--applied", type=str, help="Path to repair_events_applied_*.json")
    ap.add_argument("--base-url", type=str, default="http://127.0.0.1:5000", help="Base URL for local API server")
    args = ap.parse_args()

    base_dir = Path("backend/scripts")
    if args.backup and args.applied:
        backup_path = Path(args.backup)
        applied_path = Path(args.applied)
    else:
        found = _find_latest_applied_script(base_dir)
        if not found:
            raise SystemExit("Could not find backup/applied files under backend/scripts")
        backup_path, applied_path = found

    asyncio.run(analyze_and_maybe_apply(backup_path, applied_path, args.apply, args.base_url))


if __name__ == "__main__":
    main()
