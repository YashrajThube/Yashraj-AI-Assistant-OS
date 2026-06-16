from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import logging

from sqlalchemy import and_, delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_TIMEZONE
from app.models.event_model import Event
from app.schemas.calendar_schema import CalendarCreateRequest
from app.services.event_formatting import (
    ScheduleMetadata,
    build_display_metadata_from_event,
    build_schedule_metadata,
    color_id_for_event_type,
    event_type_label,
    ensure_professional_title,
)
from app.services.audit_service import audit_event
from app.services.analytics_cache import invalidate_cached_analytics
from app.services.google_auth_service import create_google_calendar_event, delete_google_calendar_event, load_saved_credentials

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
logger = logging.getLogger(__name__)


# Calendar service owns persistence + sync metadata while keeping DB as the source of truth.
def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE)
    return value.astimezone(LOCAL_TIMEZONE)


def _build_default_description(event: Event, sync_status: str, metadata: ScheduleMetadata | None = None) -> str:
    source_title = metadata.title if metadata else event.title
    attendees = ", ".join(metadata.attendees) if metadata and metadata.attendees else "None"
    event_type = metadata.event_type if metadata else "general"
    priority = metadata.priority if metadata else "normal"
    created_at = event.created_at.astimezone(LOCAL_TIMEZONE).isoformat() if event.created_at.tzinfo else event.created_at.replace(tzinfo=LOCAL_TIMEZONE).isoformat()
    prompt = metadata.original_prompt if metadata else event.title
    parsed_datetime = metadata.parsed_datetime.isoformat() if metadata and metadata.parsed_datetime else event.start_time.isoformat()
    duration_minutes = metadata.duration_minutes if metadata else int((event.end_time - event.start_time).total_seconds() / 60)
    timezone_name = metadata.timezone if metadata else APP_TIMEZONE
    status_label = "Synced with Google Calendar" if sync_status == "synced" else "Pending Google Sync"

    return "\n".join(
        [
            "AI Assistant Scheduled Event",
            "",
            "Title:",
            source_title,
            "",
            "Created By:",
            "Yashraj AI Assistant",
            "",
            "Timezone:",
            timezone_name,
            "",
            "Generated From Prompt:",
            f'"{prompt}"',
            "",
            "Parsed Datetime:",
            parsed_datetime,
            "",
            "Duration Minutes:",
            str(duration_minutes),
            "",
            "Attendees:",
            attendees,
            "",
            "Event Type:",
            event_type_label(event_type),
            "",
            "Priority:",
            "High Priority" if priority == "high" else "Normal",
            "",
            "Status:",
            status_label,
            "",
            "Created At:",
            created_at,
        ]
    )


def _event_metadata_for_sync(event: Event, metadata: ScheduleMetadata | None = None) -> ScheduleMetadata:
    if metadata is not None:
        return metadata

    return build_display_metadata_from_event(
        title=event.title,
        start_time=_ensure_timezone(event.start_time),
        end_time=_ensure_timezone(event.end_time),
        timezone=APP_TIMEZONE,
        sync_status=event.sync_status,
        created_at=event.created_at,
    )


async def _find_conflict(
    db: AsyncSession,
    user_id: int,
    new_start: datetime,
    new_end: datetime,
) -> Event | None:
    statement = select(Event).where(
        Event.user_id == user_id,
        Event.start_time < new_end,
        Event.end_time > new_start,
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def _find_duplicate_event(
    db: AsyncSession,
    user_id: int,
    normalized_title: str,
    new_start: datetime,
    new_end: datetime,
) -> Event | None:
    statement = select(Event).where(
        Event.user_id == user_id,
        Event.start_time < new_end,
        Event.end_time > new_start,
        Event.title == normalized_title,
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def _sync_google_event(event: Event, metadata: ScheduleMetadata | None = None) -> tuple[str | None, str, str | None]:
    credentials = await load_saved_credentials()
    if credentials is None:
        logger.warning("Google OAuth not connected, cannot sync event_id=%s", event.id)
        return None, "pending", "Google OAuth not connected"

    payload_metadata = _event_metadata_for_sync(event, metadata)
    title = ensure_professional_title(payload_metadata.title or event.title)
    description = payload_metadata.description or _build_default_description(event, "pending", payload_metadata)
    color_id = payload_metadata.color_id or color_id_for_event_type(payload_metadata.event_type)

    try:
        google_payload = await create_google_calendar_event(
            title=title,
            start_time=event.start_time,
            end_time=event.end_time,
            description=description,
            color_id=color_id,
            attendees=payload_metadata.attendees,
            reminders=[10, 30],
        )
        google_event_id = google_payload.get("id")
        logger.info(
            json.dumps(
                {
                    "event": "GOOGLE_SYNC_SUCCESS",
                    "status": "synced",
                    "event_id": event.id,
                    "google_event_id": google_event_id,
                    "title": title,
                    "color_id": color_id,
                    "event_type": payload_metadata.event_type,
                },
                ensure_ascii=True,
            )
        )
        logger.info(
            "EVENT_SYNCED event_id=%s title=%s event_type=%s priority=%s google_event_id=%s",
            event.id,
            title,
            payload_metadata.event_type,
            payload_metadata.priority,
            google_event_id,
        )
        return google_event_id, "synced", None
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "GOOGLE_SYNC_FAILED",
                    "status": "retry_pending",
                    "event_id": event.id,
                    "error": str(exc)[:300],
                },
                ensure_ascii=True,
            ),
            exc_info=True,
        )
        logger.warning("GOOGLE_SYNC_FAILED event_id=%s error=%s", event.id, str(exc)[:300])
        return None, "retry_pending", str(exc)


async def create_event(db: AsyncSession, user_id: int, payload: CalendarCreateRequest) -> Event:
    start_time = _ensure_timezone(payload.start_time)
    end_time = _ensure_timezone(payload.end_time)
    normalized_title = ensure_professional_title(payload.title)

    conflict = await _find_conflict(db, user_id, start_time, end_time)
    if conflict is not None:
        raise ValueError("Event conflict detected: overlapping event exists in this time window")

    duplicate = await _find_duplicate_event(db, user_id, normalized_title, start_time, end_time)
    if duplicate is not None:
        raise ValueError("Duplicate event detected: same professional title overlaps an existing event")

    event = Event(
        user_id=user_id,
        title=normalized_title,
        start_time=start_time,
        end_time=end_time,
        sync_status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    metadata = build_schedule_metadata(
        original_prompt=payload.title,
        parsed_datetime=start_time,
        duration_minutes=max(1, int(round((end_time - start_time).total_seconds() / 60))),
        timezone=APP_TIMEZONE,
    )
    if getattr(payload, "description", None):
        metadata.description = f"{metadata.description}\n\nManual Notes:\n{payload.description.strip()}"
    event._schedule_metadata = metadata
    audit_event(
        event="calendar_event",
        actor=user_id,
        action="create",
        details={"title": metadata.title, "event_type": metadata.event_type, "priority": metadata.priority},
    )
    invalidate_cached_analytics(user_id)
    logger.info(
        "EVENT_CREATED event_id=%s title=%s event_type=%s priority=%s start_time=%s end_time=%s",
        event.id,
        event.title,
        metadata.event_type,
        metadata.priority,
        event.start_time,
        event.end_time,
    )
    return event


def serialize_calendar_event(event: Event, metadata: ScheduleMetadata | None = None, notes: str | None = None) -> dict:
    if metadata is None:
        metadata = build_display_metadata_from_event(
            title=event.title,
            start_time=_ensure_timezone(event.start_time),
            end_time=_ensure_timezone(event.end_time),
            timezone=APP_TIMEZONE,
            sync_status=event.sync_status,
            created_at=event.created_at,
            notes=notes,
        )

    return {
        "id": event.id,
        "user_id": event.user_id,
        "title": metadata.title,
        "start_time": _ensure_timezone(event.start_time).isoformat(),
        "end_time": _ensure_timezone(event.end_time).isoformat(),
        "description": metadata.description,
        "attendees": metadata.attendees,
        "timezone": metadata.timezone,
        "event_type": metadata.event_type,
        "event_type_label": event_type_label(metadata.event_type),
        "priority": metadata.priority,
        "priority_label": "High Priority" if metadata.priority == "high" else "Normal",
        "confidence": metadata.confidence,
        "original_prompt": metadata.original_prompt,
        "parsed_datetime": metadata.parsed_datetime.isoformat() if metadata.parsed_datetime else None,
        "duration_minutes": metadata.duration_minutes,
        "color_id": metadata.color_id,
        "duplicate_risk": metadata.duplicate_risk,
        "sync_status": event.sync_status,
        "google_event_id": event.google_event_id,
        "sync_error": event.sync_error,
        "created_at": (event.created_at or datetime.now(timezone.utc)).isoformat(),
    }


async def sync_google_event_for_retry(db: AsyncSession, event_id: int, metadata: ScheduleMetadata | None = None) -> Event:
    statement = select(Event).where(Event.id == event_id)
    event = (await db.execute(statement)).scalar_one_or_none()
    if event is None:
        raise ValueError(f"Event not found for retry sync: {event_id}")

    google_event_id, sync_status, sync_error = await _sync_google_event(event, metadata=metadata)
    event.google_event_id = google_event_id
    event.sync_status = sync_status
    event.sync_error = sync_error
    await db.commit()
    await db.refresh(event)
    invalidate_cached_analytics(event.user_id)

    if sync_status != "synced":
        raise RuntimeError(sync_error or "Google sync failed")
    return event


async def get_events(db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0) -> list[Event]:
    statement = (
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.start_time.asc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(statement)).all())


async def delete_events(db: AsyncSession, user_id: int, target_date: date | None = None) -> int:
    select_stmt = select(Event).where(Event.user_id == user_id)
    if target_date is not None:
        day_start = _ensure_timezone(datetime.combine(target_date, time.min))
        day_end = day_start + timedelta(days=1)
        select_stmt = select_stmt.where(
            Event.start_time >= day_start,
            Event.start_time < day_end,
        )

    events = list((await db.scalars(select_stmt)).all())
    if not events:
        return 0

    deletable_ids: list[int] = []
    for event in events:
        if event.google_event_id:
            try:
                await delete_google_calendar_event(event.google_event_id)
                logger.info(
                    json.dumps(
                        {
                            "event": "google_sync",
                            "status": "deleted",
                            "event_id": event.id,
                            "google_event_id": event.google_event_id,
                        },
                        ensure_ascii=True,
                    )
                )
            except Exception as exc:
                logger.error(
                    "Skipping DB delete due to Google delete failure for event_id=%s: %s",
                    event.id,
                    exc,
                    exc_info=True,
                )
                continue
        deletable_ids.append(event.id)

    if not deletable_ids:
        return 0

    result = await db.execute(sa_delete(Event).where(Event.user_id == user_id, Event.id.in_(deletable_ids)))
    await db.commit()
    audit_event(
        event="calendar_event",
        actor=user_id,
        action="delete",
        details={"deleted_count": int(result.rowcount or 0), "target_date": target_date.isoformat() if target_date else None},
    )
    invalidate_cached_analytics(user_id)
    return int(result.rowcount or 0)


async def cleanup_events(
    db: AsyncSession,
    user_id: int,
    action: str,
    before_date: date | None = None,
    event_ids: list[int] | None = None,
    shift_minutes: int = 0,
) -> dict:
    statement = select(Event).where(Event.user_id == user_id)

    filters = []
    if event_ids:
        filters.append(Event.id.in_(event_ids))
    if before_date is not None:
        day_start = _ensure_timezone(datetime.combine(before_date, time.min))
        day_end = day_start + timedelta(days=1)
        filters.append(Event.start_time < day_end)

    if filters:
        statement = statement.where(and_(*filters))

    events = list((await db.scalars(statement)).all())
    matched_ids = [event.id for event in events]

    if action == "delete":
        if matched_ids:
            await db.execute(sa_delete(Event).where(Event.user_id == user_id, Event.id.in_(matched_ids)))
            await db.commit()
        return {
            "success": True,
            "action": action,
            "matched": len(matched_ids),
            "affected": len(matched_ids),
            "event_ids": matched_ids,
        }

    if action == "shift":
        if shift_minutes == 0:
            return {
                "success": False,
                "action": action,
                "matched": len(matched_ids),
                "affected": 0,
                "event_ids": matched_ids,
            }

        delta = timedelta(minutes=shift_minutes)
        for event in events:
            event.start_time = _ensure_timezone(event.start_time) + delta
            event.end_time = _ensure_timezone(event.end_time) + delta
            event.sync_status = "retry_pending"
            event.sync_error = "Event shifted; Google sync should be retried"

        await db.commit()
        return {
            "success": True,
            "action": action,
            "matched": len(matched_ids),
            "affected": len(matched_ids),
            "event_ids": matched_ids,
        }

    raise ValueError(f"Unsupported cleanup action: {action}")


async def create_event_from_intent(
    db: AsyncSession,
    user_id: int,
    title: str,
    start_time: datetime,
    end_time: datetime,
) -> Event:
    payload = CalendarCreateRequest(title=title, start_time=start_time, end_time=end_time)
    return await create_event(db, user_id, payload)
