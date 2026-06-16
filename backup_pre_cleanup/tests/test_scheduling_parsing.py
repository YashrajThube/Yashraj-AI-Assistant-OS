from app.services.intent_service import extract_datetime, extract_duration_hours, strip_datetime_phrases
from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.config import APP_TIMEZONE

LOCAL = ZoneInfo(APP_TIMEZONE)


def test_extract_duration_hours_examples():
    assert extract_duration_hours("Schedule a 2-hour meeting") == 2.0
    assert extract_duration_hours("2 hrs") == 2.0
    assert extract_duration_hours("30 minutes") == 0.5
    assert extract_duration_hours("No duration here") == 1.0


def test_extract_datetime_range_phrase():
    text = "Schedule a 2-hour meeting with Alice on 25 May 2026 from 3:00 PM to 5:00 PM for planning."
    dt = extract_datetime(text)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 25
    # hour should be 15 in local timezone
    assert dt.hour == 15


def test_strip_datetime_phrases_removes_time():
    text = "Schedule a 2-hour meeting with Bob tomorrow at 9pm for sync"
    stripped = strip_datetime_phrases(text)
    assert "tomorrow" not in stripped.lower()
    assert "9pm" not in stripped.lower()
    assert "Schedule" in stripped or "meeting" in stripped
