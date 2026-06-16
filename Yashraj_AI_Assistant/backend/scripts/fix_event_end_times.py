"""
Dry-run migration to fix events where end_time <= start_time or where
the stored duration appears incorrect. By default this script performs a
dry-run and prints proposed updates. To apply changes pass `--apply`.

Usage:
  python fix_event_end_times.py [--apply]
"""
import argparse
import asyncio
from datetime import timedelta

from sqlalchemy import text
from app.db.database import SessionLocal
from app.models.event_model import Event
from app.services.intent_service import extract_duration_hours


async def main(apply: bool):
    async with SessionLocal() as session:
        # Find events where end_time <= start_time OR duration > 24h OR implausible years
        rows = await session.execute(
            text("SELECT id, start_time, end_time, title FROM events")
        )
        candidates = rows.fetchall()

        to_update = []
        backup = []
        from datetime import datetime as _dt
        now = _dt.now()
        for r in candidates:
            eid, start_time, end_time, title = r
            if end_time is None or start_time is None:
                continue
            implausible_year = start_time.year > (now.year + 5) or end_time.year > (now.year + 5)
            if end_time <= start_time or (end_time - start_time) > timedelta(days=1) or implausible_year:
                # Try to infer duration from title
                duration_hours = extract_duration_hours(title or "")
                # If year is implausible, shift the start date to the nearest plausible year
                new_start = start_time
                if implausible_year:
                    try:
                        # Prefer the same month/day in the current year or next year if date already passed
                        candidate = start_time.replace(year=now.year)
                        if candidate < now:
                            candidate = candidate.replace(year=now.year + 1)
                        new_start = candidate
                    except Exception:
                        new_start = start_time

                new_end = new_start + timedelta(hours=duration_hours)
                to_update.append((eid, start_time, end_time, new_start, new_end, duration_hours, title))
                backup.append({"id": eid, "start_time": str(start_time), "end_time": str(end_time), "title": title})

        if not to_update:
            print("No candidate events found for repair.")
            return

        print(f"Found {len(to_update)} events to repair (dry-run):")
        for eid, start, old_end, new_start, new_end, hours, title in to_update:
            print(
                f"- event_id={eid} start={start} old_end={old_end} -> new_start={new_start} new_end={new_end} (duration_hours={hours}) title={title}"
            )

        # Write backup file for safety
        import json, time
        backup_path = f"backend/scripts/repair_events_backup_{int(time.time())}.json"
        with open(backup_path, "w", encoding="utf-8") as bf:
            json.dump(backup, bf, indent=2)
        print(f"Backup written to {backup_path}")

        if not apply:
            print("Dry-run complete. Rerun with --apply to commit changes.")
            return

        # Apply updates
        applied = []
        for eid, start, old_end, new_start, new_end, hours, title in to_update:
            # update start_time and end_time where needed
            await session.execute(
                text("UPDATE events SET start_time = :start, end_time = :end WHERE id = :id"),
                {"start": new_start, "end": new_end, "id": eid},
            )
            applied.append({
                "id": eid,
                "old_start": str(start),
                "old_end": str(old_end),
                "new_start": str(new_start),
                "new_end": str(new_end),
                "duration_hours": hours,
                "title": title,
            })
        await session.commit()
        print(f"Applied updates to {len(applied)} events.")

        # Write applied changes report and log repaired IDs
        import time, logging, json
        report_path = f"backend/scripts/repair_events_applied_{int(time.time())}.json"
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(applied, rf, indent=2)
        logging.basicConfig(filename='backend/scripts/repair_events.log', level=logging.INFO)
        logging.info("Applied repairs to event ids: %s", [a['id'] for a in applied])
        print(f"Applied changes written to {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply updates to the DB")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
