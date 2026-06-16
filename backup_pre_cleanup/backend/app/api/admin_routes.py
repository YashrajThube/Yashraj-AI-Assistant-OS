import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_TIMEZONE
from app.core.responses import ok_response, error_response
from app.db.database import SessionLocal, get_db
from app.schemas.calendar_schema import CalendarCreateRequest
from app.services.calendar_service import create_event, get_events, serialize_calendar_event, sync_google_event_for_retry
from app.models.event_model import Event

router = APIRouter(prefix="/api/admin", tags=["admin"]) 
logger = logging.getLogger(__name__)


@router.post("/sync_pending")
async def sync_pending_events():
    results = []
    try:
        async with SessionLocal() as db:  # type: AsyncSession
            events = await get_events(db, user_id=1, limit=1000, offset=0)
            for ev in events:
                if ev.sync_status == "synced":
                    continue
                try:
                    synced_event = await sync_google_event_for_retry(db, ev.id)
                    results.append(
                        {
                            "id": synced_event.id,
                            "status": synced_event.sync_status,
                            "google_event_id": synced_event.google_event_id,
                            "error": synced_event.sync_error,
                        }
                    )
                except Exception as exc:
                    logger.exception("Failed to sync event %s", ev.id)
                    results.append({"id": ev.id, "status": "failed", "error": str(exc)})
    except Exception as exc:
        logger.exception("Admin sync failed")
        return error_response(message="Failed to sync pending events", status_code=503)

    return ok_response(data={"results": results}, message="Pending events sync attempted")


@router.post("/test_google_sync")
async def test_google_sync():
    try:
        async with SessionLocal() as db:
            ist_now = datetime.now(ZoneInfo(APP_TIMEZONE))
            tomorrow = ist_now.replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=1)
            payload = CalendarCreateRequest(
                title="System Sync Verification",
                start_time=tomorrow,
                end_time=tomorrow + timedelta(hours=1),
            )
            try:
                event = await create_event(db, user_id=1, payload=payload)
            except ValueError as exc:
                if "conflict" not in str(exc).lower():
                    raise

                logger.warning(
                    "ADMIN_TEST_GOOGLE_SYNC_SLOT_CONFLICT requested_start=%s requested_end=%s",
                    payload.start_time,
                    payload.end_time,
                )
                overlap = (
                    await db.execute(
                        select(Event).where(
                            Event.user_id == 1,
                            Event.start_time < payload.end_time,
                            Event.end_time > payload.start_time,
                        )
                    )
                ).scalar_one_or_none()
                if overlap is None:
                    raise
                event = overlap

            synced_event = await sync_google_event_for_retry(db, event.id)
            metadata = getattr(event, "_schedule_metadata", None)
            logger.info(
                "ADMIN_TEST_GOOGLE_SYNC_SUCCESS event_id=%s google_event_id=%s",
                synced_event.id,
                synced_event.google_event_id,
            )
            return ok_response(
                data={
                    "event": serialize_calendar_event(synced_event, metadata=metadata, notes=payload.description),
                    "connected": True,
                    "reused_existing_event": event.id != synced_event.id or event.title != payload.title,
                },
                message="Admin test Google sync completed",
            )
    except Exception as exc:
        logger.exception("Admin test Google sync failed")
        return error_response(message=f"Failed to run test Google sync: {exc}", status_code=503)
