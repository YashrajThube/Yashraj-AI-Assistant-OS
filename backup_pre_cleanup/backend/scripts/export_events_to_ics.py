"""Export calendar events from the running backend to a .ics file.

Usage:
  python export_events_to_ics.py [--only-pending]

The script calls the local backend at http://127.0.0.1:5000/api/calendar/events
and writes `calendar_export.ics` in the current working directory.
"""
from __future__ import annotations
import requests
import sys
from datetime import datetime
from typing import List

API = "http://127.0.0.1:5000/api/calendar/events"


def fetch_events() -> List[dict]:
    r = requests.get(API, timeout=10)
    r.raise_for_status()
    payload = r.json()
    return payload.get("data", {}).get("events", [])


def format_dt(iso: str) -> str:
    # Convert ISO local datetime like 2026-05-24T21:00:00 to ICS DTSTART format YYYYMMDDTHHMMSS
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        # fallback: return raw
        return iso.replace('-', '').replace(':', '').split('.')[0]
    return dt.strftime('%Y%m%dT%H%M%S')


def to_ics(events: List[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Yashraj AI Assistant//EN",
    ]

    now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

    for ev in events:
        uid = ev.get('google_event_id') or f"local-{ev.get('id')}"
        dtstart = format_dt(ev.get('start_time') or '')
        dtend = format_dt(ev.get('end_time') or '')
        summary = ev.get('title', 'Event')

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
        ]
        if dtstart:
            lines.append(f"DTSTART:{dtstart}")
        if dtend:
            lines.append(f"DTEND:{dtend}")
        lines += [
            f"SUMMARY:{summary}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    only_pending = '--only-pending' in sys.argv
    events = fetch_events()
    if only_pending:
        events = [e for e in events if e.get('sync_status') != 'synced']

    if not events:
        print('No events found to export.')
        return

    ics = to_ics(events)
    out = 'calendar_export.ics'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(ics)

    print(f'Wrote {len(events)} events to {out}. Import this file into Google Calendar.')


if __name__ == '__main__':
    main()
