from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.calendar_service import delete_events
from app.services.intent_service import extract_delete_date


# Deletion logic is separated to keep assistant orchestration minimal and explicit.
async def handle_delete_intent(db: AsyncSession, user_id: int, text: str) -> dict[str, Any]:
    target_date = extract_delete_date(text)
    deleted = await delete_events(db, user_id, target_date=target_date)

    if target_date:
        when_label = target_date.isoformat()
        return {
            "success": True,
            "intent": "delete",
            "response": f"Deleted {deleted} meeting(s) for {when_label}.",
            "deleted": deleted,
            "event": None,
        }

    return {
        "success": True,
        "intent": "delete",
        "response": f"Deleted {deleted} meeting(s).",
        "deleted": deleted,
        "event": None,
    }
