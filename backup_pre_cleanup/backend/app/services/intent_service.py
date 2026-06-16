import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates

from app.core.config import APP_TIMEZONE

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
IntentType = Literal["schedule", "delete", "chat"]


# Intent detection and time extraction live in this module to keep the orchestrator service focused.
def detect_schedule_intent(text: str) -> bool:
    lowered = text.lower()
    keywords = ["schedule", "meeting", "appointment", "calendar", "book", "set up", "remind", "reminder"]
    if any(keyword in lowered for keyword in keywords):
        return True

    has_time_or_date = bool(
        re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lowered)
        or re.search(r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
        or re.search(r"\bevery\b", lowered)
    )
    has_action_word = any(keyword in lowered for keyword in ["create", "plan", "sync", "set", "arrange"])
    return has_time_or_date and has_action_word


def detect_delete_intent(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "delete meeting",
        "delete meetings",
        "delete event",
        "delete events",
        "delete all meeting",
        "delete all meetings",
        "delete all event",
        "delete all events",
        "clear meeting",
        "clear meetings",
        "clear events",
        "remove meetings",
        "remove events",
        "cancel all meetings",
        "cancel meeting",
        "cancel events",
    ]
    return any(keyword in lowered for keyword in keywords)


def detect_intent(text: str) -> IntentType:
    if detect_delete_intent(text):
        return "delete"
    if detect_schedule_intent(text):
        return "schedule"
    return "chat"


def extract_delete_date(text: str) -> date | None:
    lowered = text.lower()
    if "tomorrow" in lowered:
        return (datetime.now(LOCAL_TIMEZONE) + timedelta(days=1)).date()
    if "today" in lowered:
        return datetime.now(LOCAL_TIMEZONE).date()

    parsed = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if parsed:
        return parsed.date()
    return None


def extract_duration_hours(text: str) -> float:
    """Extract duration in hours from free text.

    Supports forms like:
    - "2 hours", "2 hour"
    - "2-hour" (hyphenated)
    - "2 hrs", "2hr", "2h"
    - minutes ("30 minutes") which are converted to fractional hours

    Returns a float number of hours, bounded between 0.25 and 8.
    Defaults to 1.0 when no duration phrase is found.
    """
    lowered = text.lower()

    # Hours: matches '2 hour', '2-hour', '2hr', '2 h', '2hrs'
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:-?\s*)(?:hours?|hrs?|h|hr)\b", lowered)
    if m:
        try:
            value = float(m.group(1))
        except Exception:
            value = 1.0
        return max(0.25, min(value, 8.0))

    # Minutes: '30 minutes', '45 mins', '90-minute' (hyphenated)
    m2 = re.search(r"\b(\d+)\s*(?:-?\s*)?(?:minutes?|mins|min)\b", lowered)
    if m2:
        try:
            mins = int(m2.group(1))
            hours = mins / 60.0
        except Exception:
            hours = 1.0
        return max(0.25, min(hours, 8.0))

    return 1.0


def _extract_relative_offset_datetime(text: str) -> datetime | None:
    lowered = text.lower()
    match = re.search(r"\bafter\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b", lowered)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    now = datetime.now(LOCAL_TIMEZONE)

    if unit.startswith("min"):
        return now + timedelta(minutes=amount)
    if unit.startswith("hour") or unit.startswith("hr"):
        return now + timedelta(hours=amount)
    return now + timedelta(days=amount)


def _extract_weekday_datetime(text: str) -> datetime | None:
    lowered = text.lower()
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    weekday_name = next((name for name in weekdays if re.search(rf"\b(?:every\s+)?{name}\b", lowered)), None)
    if weekday_name is None:
        return None

    time_parts = _extract_time_components(lowered)
    if time_parts is None:
        return None

    now = datetime.now(LOCAL_TIMEZONE)
    target_weekday = weekdays[weekday_name]
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and now.time() >= time(*time_parts):
        days_ahead = 7

    target_date = (now + timedelta(days=days_ahead)).date()
    hour, minute = time_parts
    return datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=hour,
        minute=minute,
        tzinfo=LOCAL_TIMEZONE,
    )


def _strip_duration_phrase(text: str) -> str:
    cleaned = re.sub(r"\bfor\s+\d+\s*(hour|hours|hr|hrs)\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_time_components(text: str) -> tuple[int, int] | None:
    explicit = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE)
    fallback = re.search(r"\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?\b|\b(\d{1,2})\s*(am|pm)\b", text, re.IGNORECASE)
    match = explicit or fallback
    if not match:
        return None

    groups = match.groups()
    if explicit:
        hour = int(groups[0])
        minute = int(groups[1] or 0)
        meridiem = (groups[2] or "").lower()
    else:
        if groups[0] is not None:
            hour = int(groups[0])
            minute = int(groups[1] or 0)
            meridiem = (groups[2] or "").lower()
        else:
            hour = int(groups[3])
            minute = 0
            meridiem = (groups[4] or "").lower()

    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _has_explicit_date_marker(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "today",
        "tomorrow",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    if any(token in lowered for token in keywords):
        return True
    if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", lowered):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", lowered):
        return True
    return False


def _normalize_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE)
    return value.astimezone(LOCAL_TIMEZONE)


def extract_datetime(text: str) -> datetime | None:
    cleaned_text = _strip_duration_phrase(text)

    relative_offset_dt = _extract_relative_offset_datetime(cleaned_text)
    if relative_offset_dt is not None:
        return relative_offset_dt.replace(second=0, microsecond=0)

    weekday_dt = _extract_weekday_datetime(cleaned_text)
    if weekday_dt is not None:
        return weekday_dt.replace(second=0, microsecond=0)

    time_parts = _extract_time_components(cleaned_text)

    if time_parts and not _has_explicit_date_marker(cleaned_text):
        hour, minute = time_parts
        now = datetime.now(LOCAL_TIMEZONE)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    direct = dateparser.parse(
        cleaned_text,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": APP_TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    # Guard: if dateparser.parse returns an implausible year (caused by
    # mis-parsing numeric tokens like '90-minute'), ignore the direct result
    # and fall back to `search_dates`.
    try:
        from datetime import datetime as _dt

        if direct and getattr(direct, "year", 0) > (_dt.now().year + 5):
            direct = None
    except Exception:
        pass
    if direct:
        if time_parts:
            hour, minute = time_parts
            direct = direct.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return _normalize_local_datetime(direct)

    relative_base = datetime.now(LOCAL_TIMEZONE)
    results = search_dates(
        cleaned_text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": relative_base,
            "TIMEZONE": APP_TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if not results:
        return None

    candidates = []
    for raw_text, parsed_dt in results:
        lowered = raw_text.lower()
        # Skip obvious duration tokens like '90-minute', '30 minutes', '2-hour'
        if re.search(r"\b\d+\s*(?:-?\s*)?(?:minute|minutes|min|mins|hour|hours|hr|hrs)\b", lowered):
            continue
        # Skip bare numeric matches which dateparser may interpret as a year (e.g. '90')
        if re.fullmatch(r"\d{1,4}", lowered):
            continue
        # Skip implausible years far in the future (guard against bad parses)
        try:
            from datetime import datetime as _dt

            if parsed_dt.year > (_dt.now().year + 5):
                continue
        except Exception:
            pass
        score = 0
        if "at" in lowered:
            score += 2
        if re.search(r"\b(am|pm)\b", lowered):
            score += 2
        if re.search(r"\b\d{1,2}:\d{2}\b", lowered):
            score += 1
        score += min(len(raw_text), 50) / 100
        candidates.append((score, parsed_dt))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = candidates[0][1]
    else:
        results.sort(key=lambda item: len(item[0]), reverse=True)
        selected = results[0][1]

    if time_parts:
        hour, minute = time_parts
        selected = selected.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return _normalize_local_datetime(selected)


def strip_datetime_phrases(text: str) -> str:
    """Return `text` with date/time/duration phrases removed.

    Uses `search_dates` to remove natural-language date spans and a few
    targeted regexes for common time/duration phrases so what's left can
    be used as an event title/subject.
    """
    if not text:
        return ""

    cleaned = text

    try:
        results = search_dates(
            text,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": APP_TIMEZONE,
                "RETURN_AS_TIMEZONE_AWARE": True,
            },
        )
    except Exception:
        results = None

    if results:
        for raw_text, _ in results:
            # Remove exact matched span occurrences from the input
            cleaned = re.sub(re.escape(raw_text), "", cleaned, flags=re.IGNORECASE)

    # Remove explicit time markers like "at 9pm", "at 09:00 am"
    cleaned = re.sub(r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", cleaned, flags=re.IGNORECASE)
    # Remove explicit range phrases like "from 3:00 PM to 5:00 PM"
    cleaned = re.sub(r"\bfrom\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+to\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", "", cleaned, flags=re.IGNORECASE)
    # Remove hyphenated durations like "2-hour"
    cleaned = re.sub(r"\b\d+(?:\.\d+)?-hour\b", "", cleaned, flags=re.IGNORECASE)
    # Remove leftover 'to <time>' fragments (e.g., from 'to 5:00 PM')
    cleaned = re.sub(r"\bto\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", cleaned, flags=re.IGNORECASE)
    # Remove relative phrases like "today", "tomorrow", "tonight"
    cleaned = re.sub(r"\b(today|tomorrow|tonight)\b", "", cleaned, flags=re.IGNORECASE)
    # Remove duration phrases e.g. "for 2 hours"
    cleaned = re.sub(r"\bfor\s+\d+\s*(hour|hours|hr|hrs)\b", "", cleaned, flags=re.IGNORECASE)
    # Remove relative offsets like "after 30 minutes"
    cleaned = re.sub(r"\bafter\s+\d+\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b", "", cleaned, flags=re.IGNORECASE)

    # Remove common polite lead-ins
    cleaned = re.sub(r"\b(?:please|pls|can you|could you|would you)\b", "", cleaned, flags=re.IGNORECASE)

    # Strip leftover punctuation and collapse whitespace
    cleaned = re.sub(r"[,:\-()\"]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
