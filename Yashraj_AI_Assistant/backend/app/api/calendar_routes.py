from datetime import datetime, timedelta
import logging
import asyncio
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import error_response, ok_response
from app.db.database import SessionLocal, get_db
from app.services.retry_service import create_failed_job, run_retry_job
from app.schemas.calendar_schema import CalendarCreateRequest, CalendarCleanupRequest
from app.services.calendar_service import cleanup_events, create_event, delete_events, get_events, serialize_calendar_event, sync_google_event_for_retry
from app.core.config import APP_TIMEZONE

router = APIRouter(prefix="/api/calendar", tags=["calendar"])
DEFAULT_USER_ID = 1
logger = logging.getLogger(__name__)


async def enqueue_google_sync(event_id: int) -> None:
    async with SessionLocal() as db:
        try:
            logger.info(json.dumps({"event": "calendar_sync", "stage": "retry_start", "event_id": event_id}, ensure_ascii=True))
            await sync_google_event_for_retry(db, event_id)
            logger.info(json.dumps({"event": "calendar_sync", "stage": "retry_success", "event_id": event_id}, ensure_ascii=True))
        except Exception as exc:
            logger.error(
                json.dumps(
                    {"event": "calendar_sync", "stage": "retry_failed", "event_id": event_id, "error": str(exc)[:500]},
                    ensure_ascii=True,
                ),
                exc_info=True,
            )
            failed = await create_failed_job(db, job_type="google_sync", payload={"event_id": event_id})
            asyncio.create_task(run_retry_job(failed.id))


async def _sync_event_now(db: AsyncSession, event_id: int) -> object:
    logger.info(json.dumps({"event": "calendar_sync", "stage": "sync_start", "event_id": event_id}, ensure_ascii=True))
    synced_event = await sync_google_event_for_retry(db, event_id)
    logger.info(
        json.dumps(
            {
                "event": "calendar_sync",
                "stage": "sync_success",
                "event_id": synced_event.id,
                "google_event_id": synced_event.google_event_id,
                "sync_status": synced_event.sync_status,
            },
            ensure_ascii=True,
        ),
    )
    return synced_event


@router.post("/create")
async def create_calendar_event(
    payload: CalendarCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info(
            json.dumps(
                {
                    "event": "calendar_create",
                    "stage": "request_received",
                    "title": payload.title,
                    "start_time": payload.start_time.isoformat(),
                    "end_time": payload.end_time.isoformat(),
                    "timezone": APP_TIMEZONE,
                },
                ensure_ascii=True,
            )
        )
        event = await create_event(db, DEFAULT_USER_ID, payload)
        logger.info(
            json.dumps(
                {
                    "event": "calendar_create",
                    "stage": "db_saved",
                    "event_id": event.id,
                    "sync_status": event.sync_status,
                    "title": event.title,
                },
                ensure_ascii=True,
            )
        )

        metadata = getattr(event, "_schedule_metadata", None)
        synced_event = event
        try:
            synced_event = await _sync_event_now(db, event.id)
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "calendar_create",
                        "stage": "sync_failed",
                        "event_id": event.id,
                        "error": str(exc)[:500],
                    },
                    ensure_ascii=True,
                ),
                exc_info=True,
            )
            background_tasks.add_task(enqueue_google_sync, event.id)
    except ValueError as exc:
        return error_response(message=str(exc), status_code=409)
    except Exception:
        logger.exception("API error while creating calendar event")
        return error_response(message="Failed to create calendar event", status_code=503)

    metadata = getattr(synced_event, "_schedule_metadata", None) or metadata
    return ok_response(
        data={"event": serialize_calendar_event(synced_event, metadata=metadata, notes=payload.description)},
        message="Calendar event created",
    )


@router.get("/events")
async def list_calendar_events(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        events = [serialize_calendar_event(item) for item in await get_events(db, DEFAULT_USER_ID, limit=limit, offset=offset)]
    except Exception:
        logger.exception("API error while listing calendar events")
        return error_response(message="Failed to fetch calendar events", status_code=503)

    return ok_response(data={"events": events}, message="Calendar events fetched")


@router.delete("/events")
async def delete_calendar_events(
    date: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    target_date = None
    if date:
        try:
            target_date = datetime.fromisoformat(date).date()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="date must be ISO format YYYY-MM-DD") from exc

    try:
        deleted = await delete_events(db, DEFAULT_USER_ID, target_date=target_date)
    except Exception:
        logger.exception("API error while deleting calendar events")
        return error_response(message="Failed to delete calendar events", status_code=503)

    return ok_response(data={"deleted": deleted}, message="Calendar events deleted")


@router.post("/cleanup")
async def cleanup_calendar_events(
    payload: CalendarCleanupRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await cleanup_events(
            db,
            user_id=DEFAULT_USER_ID,
            action=payload.action,
            before_date=payload.before_date,
            event_ids=payload.event_ids,
            shift_minutes=payload.shift_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("API error while cleaning calendar events")
        return error_response(message="Failed to cleanup calendar events", status_code=503)

    return ok_response(data=result, message="Calendar cleanup completed")


@router.post("/test_google_sync")
async def test_google_sync(db: AsyncSession = Depends(get_db)):
    try:
        ist_now = datetime.now(ZoneInfo(APP_TIMEZONE))
        tomorrow = ist_now.replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=1)
        payload = CalendarCreateRequest(
            title="System Sync Verification",
            start_time=tomorrow,
            end_time=tomorrow + timedelta(hours=1),
        )
        event = await create_event(db, DEFAULT_USER_ID, payload)
        synced_event = await _sync_event_now(db, event.id)
        metadata = getattr(event, "_schedule_metadata", None)
        logger.info(
            json.dumps(
                {
                    "event": "calendar_test_sync",
                    "stage": "completed",
                    "event_id": synced_event.id,
                    "google_event_id": synced_event.google_event_id,
                },
                ensure_ascii=True,
            )
        )
        return ok_response(
            data={
                "event": serialize_calendar_event(synced_event, metadata=metadata, notes=payload.description),
                "connected": True,
            },
            message="Test Google sync completed",
        )
    except Exception as exc:
        logger.error(
            json.dumps(
                {"event": "calendar_test_sync", "stage": "failed", "error": str(exc)[:500]},
                ensure_ascii=True,
            ),
            exc_info=True,
        )
        return error_response(message="Test Google sync failed", status_code=503)
