import asyncio
from types import SimpleNamespace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.config import APP_TIMEZONE
from app.services import scheduling_service

LOCAL = ZoneInfo(APP_TIMEZONE)


async def _fake_create_event(db, user_id, title, start_time, end_time):
    ev = SimpleNamespace()
    ev.id = 999
    ev.user_id = user_id
    ev.title = title
    ev.start_time = start_time
    ev.end_time = end_time
    ev.google_event_id = None
    ev.sync_status = "pending"
    return ev


async def _fake_sync(db, event_id, metadata=None):
    # Return an object similar to Event with google_event_id populated
    ev = SimpleNamespace()
    ev.id = event_id
    ev.google_event_id = "fake_google_id"
    return ev


async def _fake_events_for_slot(db, user_id, limit=100, offset=0):
    day = (datetime.now(LOCAL) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        SimpleNamespace(title="Busy 9am", start_time=day.replace(hour=9, minute=0), end_time=day.replace(hour=10, minute=0), sync_status="synced", created_at=day),
        SimpleNamespace(title="Lunch block", start_time=day.replace(hour=12, minute=0), end_time=day.replace(hour=13, minute=0), sync_status="synced", created_at=day),
    ]


def _run_async(coro):
    return asyncio.run(coro)


def test_handle_schedule_explicit_range(monkeypatch):
    monkeypatch.setattr(scheduling_service, "create_event_from_intent", _fake_create_event)
    monkeypatch.setattr(scheduling_service, "sync_google_event_for_retry", _fake_sync)

    text = "Schedule a 2-hour meeting with Kalpesh on 25 May 2041 from 3:00 PM to 5:00 PM for project work."
    result = _run_async(scheduling_service.handle_schedule_intent(None, 1, text))
    assert result["success"] is True
    ev = result["event"]
    assert ev["start_time"].startswith("2041-05-25T15:00:00")
    assert ev["end_time"].startswith("2041-05-25T17:00:00")


def test_handle_schedule_duration_phrases(monkeypatch):
    monkeypatch.setattr(scheduling_service, "create_event_from_intent", _fake_create_event)
    monkeypatch.setattr(scheduling_service, "sync_google_event_for_retry", _fake_sync)

    text = "Schedule a 90-minute meeting with team tomorrow at 10am for planning."
    result = _run_async(scheduling_service.handle_schedule_intent(None, 1, text))
    assert result["success"] is True
    ev = result["event"]
    # duration should be 1.5 hours
    start = datetime.fromisoformat(ev["start_time"])
    end = datetime.fromisoformat(ev["end_time"])
    delta = end - start
    assert abs(delta.total_seconds() - 90 * 60) < 5


def test_handle_schedule_short_duration_default(monkeypatch):
    monkeypatch.setattr(scheduling_service, "create_event_from_intent", _fake_create_event)
    monkeypatch.setattr(scheduling_service, "sync_google_event_for_retry", _fake_sync)

    text = "Schedule meeting tomorrow at 9am"  # default duration 1 hour
    result = _run_async(scheduling_service.handle_schedule_intent(None, 1, text))
    assert result["success"] is True
    ev = result["event"]
    start = datetime.fromisoformat(ev["start_time"])
    end = datetime.fromisoformat(ev["end_time"])
    delta = end - start
    assert abs(delta.total_seconds() - 3600) < 5


def test_handle_schedule_autoplans_best_slot(monkeypatch):
    monkeypatch.setattr(scheduling_service, "get_events", _fake_events_for_slot)
    monkeypatch.setattr(scheduling_service, "create_event_from_intent", _fake_create_event)
    monkeypatch.setattr(scheduling_service, "sync_google_event_for_retry", _fake_sync)

    text = "Schedule tomorrow"
    result = _run_async(scheduling_service.handle_schedule_intent(SimpleNamespace(), 1, text))

    assert result["success"] is True
    ev = result["event"]
    start = datetime.fromisoformat(ev["start_time"])
    assert start.hour == 10
    assert ev["auto_planned"] is True
    assert "best available slot" in result["response"].lower()


def test_handle_schedule_conflict_reports_alternative(monkeypatch):
    async def fake_events(db, user_id, limit=100, offset=0):
        day = (datetime.now(LOCAL) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            SimpleNamespace(title="Team Sync", start_time=day.replace(hour=10, minute=0), end_time=day.replace(hour=11, minute=0), sync_status="synced", created_at=day),
            SimpleNamespace(title="Client Call", start_time=day.replace(hour=11, minute=0), end_time=day.replace(hour=12, minute=0), sync_status="synced", created_at=day),
        ]

    monkeypatch.setattr(scheduling_service, "get_events", fake_events)
    monkeypatch.setattr(scheduling_service, "create_event_from_intent", _fake_create_event)
    monkeypatch.setattr(scheduling_service, "sync_google_event_for_retry", _fake_sync)

    text = "Schedule client meeting tomorrow at 10am"
    result = _run_async(scheduling_service.handle_schedule_intent(SimpleNamespace(), 1, text))

    assert result["success"] is True
    ev = result["event"]
    start = datetime.fromisoformat(ev["start_time"])
    assert start.hour != 10
    assert ev["conflict_summary"] is not None or "alternative" in result["response"].lower()
