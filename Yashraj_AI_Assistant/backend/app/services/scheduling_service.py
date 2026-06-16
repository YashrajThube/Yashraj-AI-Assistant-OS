import re
import logging
from datetime import timedelta, datetime, date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from dateparser.search import search_dates
from dateparser import parse as dp_parse

from app.services.calendar_service import create_event_from_intent, get_events, sync_google_event_for_retry
from app.services.audit_service import audit_event
from app.services.ai_service import generate_schedule_metadata
from app.services.intent_service import extract_datetime, extract_duration_hours, strip_datetime_phrases
from app.services.scheduling_intelligence_service import plan_schedule_slot
from app.core.config import APP_TIMEZONE

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)

logger = logging.getLogger(__name__)


def _contains_explicit_time(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lowered)
        or re.search(r"\bfrom\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+to\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", lowered)
        or re.search(r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lowered)
    )


def _extract_requested_date(text: str) -> date | None:
    lowered = text.lower()
    now = datetime.now(LOCAL_TIMEZONE)
    if "tomorrow" in lowered:
        return (now + timedelta(days=1)).date()
    if "today" in lowered:
        return now.date()

    parsed = dp_parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": APP_TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if parsed is None:
        return None
    return parsed.date()


# Scheduling logic is isolated to enforce one place for parsing + event creation behavior.
async def handle_schedule_intent(db: AsyncSession, user_id: int, text: str) -> dict[str, Any]:
    parsed_datetime = extract_datetime(text)
    requested_date = _extract_requested_date(text)
    explicit_time = _contains_explicit_time(text)

    # Prefer explicit "from X to Y" ranges when present in the user's text.
    end_time = None

    # First try a focused regex for 'from <time> to <time>' which commonly
    # indicates an explicit end time.
    range_match = re.search(r"from\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\s+to\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)",
                            text,
                            flags=re.IGNORECASE)
    if range_match and parsed_datetime is not None:
        # Parse the 'to' time relative to the start_time's date. dateparser
        # sometimes fails to parse time-only fragments, so parse manually.
        time_fragment = range_match.group(2).strip()

        tmatch = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_fragment, flags=re.IGNORECASE)
        parsed_end = None
        if tmatch:
            hour = int(tmatch.group(1))
            minute = int(tmatch.group(2) or 0)
            meridiem = (tmatch.group(3) or "").lower()
            if meridiem == "pm" and hour < 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0

            parsed_end = datetime(
                year=parsed_datetime.year,
                month=parsed_datetime.month,
                day=parsed_datetime.day,
                hour=hour,
                minute=minute,
                tzinfo=LOCAL_TIMEZONE,
            )

            if parsed_end <= parsed_datetime:
                parsed_end = parsed_end + timedelta(days=1)

            end_time = parsed_end
            requested_date = parsed_datetime.date()

    if end_time is None:
        duration_hours = extract_duration_hours(text)
        duration_minutes = max(15, int(round(duration_hours * 60)))
        requested_start = parsed_datetime if explicit_time else None
        if requested_start is None and requested_date is None:
            requested_date = (datetime.now(LOCAL_TIMEZONE) + timedelta(days=1)).date()

        existing_events = await get_events(db, user_id, limit=500, offset=0) if db is not None else []
        metadata_preview = await generate_schedule_metadata(text, parsed_datetime or datetime.now(LOCAL_TIMEZONE), (parsed_datetime or datetime.now(LOCAL_TIMEZONE)) + timedelta(minutes=duration_minutes), APP_TIMEZONE)
        plan = plan_schedule_slot(
            existing_events,
            requested_start=requested_start,
            requested_date=requested_date,
            duration_minutes=duration_minutes,
            event_type=metadata_preview.event_type,
            priority=metadata_preview.priority,
            message=text,
        )
        parsed_datetime = plan.start_time
        end_time = plan.end_time
    else:
        requested_date = parsed_datetime.date()

    if parsed_datetime is None:
        parsed_datetime = datetime.now(LOCAL_TIMEZONE)

    metadata = await generate_schedule_metadata(text, parsed_datetime, end_time, APP_TIMEZONE)
    if requested_date is None:
        requested_date = parsed_datetime.date()
    title = metadata.title
    if not title or title.lower() == title:
        title = "Meeting"
        metadata.title = title

    logger.info(
        "TITLE_GENERATED title=%s confidence=%s event_type=%s attendees=%s",
        metadata.title,
        metadata.confidence,
        metadata.event_type,
        ",".join(metadata.attendees) if metadata.attendees else "none",
    )
    audit_event(
        event="assistant_schedule",
        actor=user_id,
        action="plan",
        details={
            "title": metadata.title,
            "event_type": metadata.event_type,
            "priority": metadata.priority,
            "auto_planned": bool(not explicit_time),
            "requested_date": requested_date.isoformat() if requested_date else None,
        },
    )

    try:
        logger.info("Scheduling: creating event with start_time=%s end_time=%s title=%s", parsed_datetime, end_time, title)
        event = await create_event_from_intent(db, user_id=user_id, title=title, start_time=parsed_datetime, end_time=end_time)
        logger.info("EVENT_CREATED event_id=%s title=%s", event.id, event.title)
        audit_event(
            event="assistant_schedule",
            actor=user_id,
            action="create_event",
            details={"event_id": event.id, "title": event.title, "sync_status": event.sync_status},
        )

        # CRITICAL: Sync to Google Calendar immediately after creation
        try:
            synced_event = await sync_google_event_for_retry(db, event.id, metadata=metadata)
            logger.info("GOOGLE_SYNC_SUCCESS event_id=%s google_event_id=%s", event.id, synced_event.google_event_id)
        except Exception as sync_error:
            logger.warning("GOOGLE_SYNC_FAILED event_id=%s error=%s", event.id, sync_error)
            # Event's sync_status will remain 'retry_pending' for background retry
    except ValueError as exc:
        return {
            "success": False,
            "intent": "schedule",
            "response": str(exc),
            "event": None,
            "deleted": None,
        }
    except Exception:
        return {
            "success": False,
            "intent": "schedule",
            "response": "Scheduling failed due to an internal error.",
            "event": None,
            "deleted": None,
        }

    decision_parts = []
    if not explicit_time:
        decision_parts.append(f"Best available slot selected for {event.start_time.strftime('%A %I:%M %p')}")
    if 'plan' in locals() and plan.conflict_summary:
        decision_parts.append(plan.conflict_summary)
    if 'plan' in locals() and plan.reschedule_suggestion:
        decision_parts.append(plan.reschedule_suggestion)
    if 'plan' in locals() and plan.recommendations:
        decision_parts.append(plan.recommendations[0])

    response_text = f"Meeting scheduled: {event.title} at {event.start_time}."
    if decision_parts:
        response_text = f"{response_text} {' '.join(decision_parts)}"

    return {
        "success": True,
        "intent": "schedule",
        "response": response_text,
        "event": {
            "id": event.id,
            "user_id": event.user_id,
            "title": event.title,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "description": metadata.description,
            "attendees": metadata.attendees,
            "timezone": metadata.timezone,
            "event_type": metadata.event_type,
            "confidence": metadata.confidence,
            "original_prompt": metadata.original_prompt,
            "parsed_datetime": metadata.parsed_datetime.isoformat() if metadata.parsed_datetime else None,
            "duration_minutes": metadata.duration_minutes,
            "sync_status": event.sync_status,
            "overloaded": bool(plan.overloaded) if 'plan' in locals() else False,
            "auto_planned": bool(not explicit_time or plan.auto_planned) if 'plan' in locals() else False,
            "preferred_window": plan.preferred_window if 'plan' in locals() else None,
            "recommendations": plan.recommendations if 'plan' in locals() else [],
            "conflict_summary": plan.conflict_summary if 'plan' in locals() else None,
            "reschedule_suggestion": plan.reschedule_suggestion if 'plan' in locals() else None,
        },
        "deleted": None,
    }
