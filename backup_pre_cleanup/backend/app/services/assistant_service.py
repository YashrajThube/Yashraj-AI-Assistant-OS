import logging
import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import action_executor, fallback_intent_parser, intent_parser
from app.services.audit_service import audit_event
from app.db.database import SessionLocal
from app.services.notes_service import create_note, get_recent_note_messages
from app.services.retry_service import create_failed_job, run_retry_job

logger = logging.getLogger(__name__)


def _looks_structured_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "schedule",
            "meeting",
            "appointment",
            "calendar",
            "note",
            "remember",
            "remind",
            "delete",
            "remove",
            "cancel",
            "create",
            "plan",
            "sync",
            "arrange",
        ]
    )


# Assistant orchestration composes domain services while preserving a simple route contract.
async def process_chat_message(db: AsyncSession, user_id: int, text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned:
        try:
            await create_note(db, user_id, cleaned)
        except Exception:
            logger.warning("Failed to persist chat note", exc_info=True)
    try:
        memory_messages = await get_recent_note_messages(db, user_id, limit=5)
        if not _looks_structured_request(cleaned):
            result = await action_executor(
                db,
                user_id,
                cleaned,
                {"intents": ["chat"], "data": {}},
                memory_messages,
            )
        else:
            # Command-style requests are handled locally to avoid unnecessary LLM usage.
            parsed = fallback_intent_parser(cleaned)
            logger.info("Assistant: local intent parser activated for structured command")
            result = await action_executor(db, user_id, cleaned, parsed, memory_messages)
        logger.info(
            "Assistant: processed message",
            extra={
                "user_id": user_id,
                "intent": result.get("intent"),
                "num_actions": len(result.get("actions", [])),
                "status": "success",
            },
        )
        audit_event(
            event="assistant_chat",
            actor=user_id,
            action="process_message",
            details={"intent": result.get("intent"), "num_actions": len(result.get("actions", []))},
        )
        return result
    except Exception as exc:
        logger.error(
            "Assistant: intelligent processing failed",
            extra={"user_id": user_id, "error": str(exc)[:300]},
            exc_info=True,
        )
        return {
            "intent": "chat",
            "response": "I could not process your request right now. Please try again.",
            "actions": [
                {
                    "type": "chat",
                    "status": "failed",
                    "details": {"error": "Assistant unavailable"},
                }
            ],
        }


async def process_ai_background_job(user_id: int, message: str) -> None:
    # Runs AI work after API response and records retry metadata on failure.
    async with SessionLocal() as db:
        try:
            _ = await process_chat_message(db, user_id, message)
        except Exception as exc:
            logger.error("Background AI processing failed: %s", exc, exc_info=True)
            failed = await create_failed_job(
                db,
                job_type="ai_chat",
                payload={"user_id": user_id, "message": message},
            )
            asyncio.create_task(run_retry_job(failed.id))
