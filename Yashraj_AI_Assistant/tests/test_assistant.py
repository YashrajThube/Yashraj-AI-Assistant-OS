import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.api.assistant_routes import router as assistant_router
from app.db.database import get_db


async def _fake_db_dependency():
    yield object()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(assistant_router)
    app.dependency_overrides[get_db] = _fake_db_dependency
    return app


def test_assistant_chat_background_mode(monkeypatch):
    app = _build_app()
    called = {"bg": False}

    async def fake_process_ai_background_job(user_id, message):
        called["bg"] = user_id == 1 and message == "hello there"

    async def fake_process_chat_message(db, user_id, text):
        raise AssertionError("process_chat_message should not run in background mode for chat intent")

    monkeypatch.setattr("app.api.assistant_routes.process_ai_background_job", fake_process_ai_background_job)
    monkeypatch.setattr("app.api.assistant_routes.process_chat_message", fake_process_chat_message)

    client = TestClient(app)
    response = client.post("/api/assistant/chat?background_ai=true", json={"message": "hello there"})

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["intent"] == "chat"
    assert called["bg"] is True


def test_assistant_chat_sync_mode(monkeypatch):
    app = _build_app()

    async def fake_process_chat_message(db, user_id, text):
        return {
            "intent": "chat",
            "response": "ok",
            "actions": [{"type": "chat", "status": "success"}],
        }

    monkeypatch.setattr("app.api.assistant_routes.process_chat_message", fake_process_chat_message)

    client = TestClient(app)
    response = client.post("/api/assistant/chat", json={"message": "what is ai"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["response"] == "ok"
    assert body["data"]["actions"][0]["type"] == "chat"
