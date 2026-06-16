import os
import sys
from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.api.calendar_routes import router as calendar_router
from app.api.admin_routes import router as admin_router
from app.db.database import get_db


async def _fake_db_dependency():
    yield object()


class DummySession:
    def add(self, event):
        event.id = 12
        self.event = event

    async def commit(self):
        return None

    async def refresh(self, event):
        return None

    async def execute(self, statement):
        return SimpleNamespace(scalar_one_or_none=lambda: None)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(calendar_router)
    app.include_router(admin_router)
    app.dependency_overrides[get_db] = _fake_db_dependency
    return app


def test_create_calendar_event_syncs_immediately(monkeypatch):
    app = _build_app()
    called = {"sync": False}
    called = {"sync": False, "fallback": False}

    async def fake_create_event(db, user_id, payload):
        return SimpleNamespace(
            id=11,
            user_id=user_id,
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            google_event_id=None,
            sync_status="pending",
            sync_error=None,
            created_at=payload.start_time,
            _schedule_metadata=SimpleNamespace(title=payload.title, attendees=[], timezone="Asia/Kolkata", event_type="meeting", priority="normal", confidence=0.9, parsed_datetime=payload.start_time, duration_minutes=30, color_id="9", duplicate_risk="low", description="", original_prompt=payload.title),
        )

    async def fake_sync_event_now(db, event_id):
        called["sync"] = event_id == 11
        return SimpleNamespace(
            id=11,
            user_id=1,
            title="Standup",
            start_time=datetime.fromisoformat("2026-04-10T10:00:00"),
            end_time=datetime.fromisoformat("2026-04-10T10:30:00"),
            google_event_id="google-11",
            sync_status="synced",
            sync_error=None,
            created_at=datetime.fromisoformat("2026-04-10T10:00:00"),
            _schedule_metadata=SimpleNamespace(title="Standup", attendees=[], timezone="Asia/Kolkata", event_type="meeting", priority="normal", confidence=0.9, parsed_datetime=None, duration_minutes=30, color_id="9", duplicate_risk="low", description="", original_prompt="Standup"),
        )

    async def fake_enqueue_google_sync(event_id):
        called["fallback"] = True

    monkeypatch.setattr("app.api.calendar_routes.create_event", fake_create_event)
    monkeypatch.setattr("app.api.calendar_routes._sync_event_now", fake_sync_event_now)
    monkeypatch.setattr("app.api.calendar_routes.enqueue_google_sync", fake_enqueue_google_sync)

    client = TestClient(app)
    response = client.post(
        "/api/calendar/create",
        json={
            "title": "Standup",
            "start_time": "2026-04-10T10:00:00",
            "end_time": "2026-04-10T10:30:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["event"]["id"] == 11
    assert body["data"]["event"]["title"] == "Standup"
    assert called["sync"] is True
    assert called["fallback"] is False


def test_create_calendar_event_formats_manual_input(monkeypatch):
    app = _build_app()
    called = {"sync": False}
    called = {"sync": False, "fallback": False}

    async def fake_db_dependency():
        yield DummySession()

    async def fake_find_conflict(*args, **kwargs):
        return None

    async def fake_sync_event_now(db, event_id):
        called["sync"] = event_id is not None
        return SimpleNamespace(
            id=12,
            user_id=1,
            title="Meeting with Aman",
            start_time=datetime.fromisoformat("2026-05-25T10:00:00"),
            end_time=datetime.fromisoformat("2026-05-25T11:00:00"),
            google_event_id="google-12",
            sync_status="synced",
            sync_error=None,
            created_at=datetime.fromisoformat("2026-05-25T10:00:00"),
            _schedule_metadata=SimpleNamespace(title="Meeting with Aman", attendees=["Aman"], timezone="Asia/Kolkata", event_type="meeting", priority="normal", confidence=0.9, parsed_datetime=None, duration_minutes=60, color_id="9", duplicate_risk="low", description="AI Assistant Scheduled Event\n\nManual Notes:\nmanual notes", original_prompt="meeting with aman tomorrow"),
        )

    async def fake_enqueue_google_sync(event_id):
        called["fallback"] = True

    app.dependency_overrides[get_db] = fake_db_dependency
    monkeypatch.setattr("app.api.calendar_routes._sync_event_now", fake_sync_event_now)
    monkeypatch.setattr("app.api.calendar_routes.enqueue_google_sync", fake_enqueue_google_sync)
    monkeypatch.setattr("app.services.calendar_service._find_conflict", fake_find_conflict)

    client = TestClient(app)
    response = client.post(
        "/api/calendar/create",
        json={
            "title": "meeting with aman tomorrow",
            "description": "manual notes",
            "start_time": "2026-05-25T10:00:00",
            "end_time": "2026-05-25T11:00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    event = body["data"]["event"]
    assert event["title"] == "Meeting with Aman"
    assert event["event_type"] == "meeting"
    assert event["event_type_label"] == "Meeting"
    assert event["priority"] == "normal"
    assert event["priority_label"] == "Normal"
    assert event["description"]
    assert "Manual Notes:" in event["description"]
    assert called["sync"] is True
    assert called["fallback"] is False

def test_admin_test_google_sync_endpoint(monkeypatch):
    app = _build_app()

    async def fake_create_event(db, user_id, payload):
        return SimpleNamespace(
            id=19,
            user_id=user_id,
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            google_event_id=None,
            sync_status="pending",
            sync_error=None,
            created_at=payload.start_time,
            _schedule_metadata=SimpleNamespace(title=payload.title, attendees=[], timezone="Asia/Kolkata", event_type="meeting", priority="normal", confidence=0.9, parsed_datetime=payload.start_time, duration_minutes=60, color_id="9", duplicate_risk="low", description="", original_prompt=payload.title),
        )

    async def fake_sync_google_event_for_retry(db, event_id, metadata=None):
        return SimpleNamespace(
            id=19,
            user_id=1,
            title="System Sync Verification",
            start_time=datetime.fromisoformat("2026-05-27T17:00:00+05:30"),
            end_time=datetime.fromisoformat("2026-05-27T18:00:00+05:30"),
            google_event_id="google-19",
            sync_status="synced",
            sync_error=None,
            created_at=datetime.fromisoformat("2026-05-27T17:00:00+05:30"),
        )

    monkeypatch.setattr("app.api.admin_routes.create_event", fake_create_event)
    monkeypatch.setattr("app.api.admin_routes.sync_google_event_for_retry", fake_sync_google_event_for_retry)

    client = TestClient(app)
    response = client.post("/api/admin/test_google_sync")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["connected"] is True
    assert body["data"]["event"]["google_event_id"] == "google-19"
