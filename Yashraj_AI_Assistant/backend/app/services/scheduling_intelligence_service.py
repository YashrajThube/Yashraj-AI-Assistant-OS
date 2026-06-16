from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import APP_TIMEZONE
from app.services.event_formatting import build_display_metadata_from_event
from app.services.intent_service import extract_duration_hours

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
WORKDAY_START = time(9, 0)
LUNCH_START = time(12, 0)
LUNCH_END = time(13, 0)
WORKDAY_END = time(18, 30)
SEARCH_WINDOW_DAYS = 5
SLOT_STEP_MINUTES = 15


@dataclass(slots=True)
class CalendarProfile:
    preferred_hour: int
    preferred_duration_minutes: int
    frequent_attendees: list[str]
    recurring_patterns: list[str]
    workload_ratio: float
    focus_time_score: int
    burnout_risk: str


@dataclass(slots=True)
class SchedulePlan:
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    auto_planned: bool
    overloaded: bool
    preferred_window: str
    recommendations: list[str]
    conflict_summary: str | None = None
    reschedule_suggestion: str | None = None
    chosen_reason: str | None = None


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE)
    return value.astimezone(LOCAL_TIMEZONE)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, WORKDAY_START, tzinfo=LOCAL_TIMEZONE)
    end = datetime.combine(day, WORKDAY_END, tzinfo=LOCAL_TIMEZONE)
    return start, end


def _work_segments(day: date) -> list[tuple[datetime, datetime]]:
    start, end = _day_bounds(day)
    lunch_start = datetime.combine(day, LUNCH_START, tzinfo=LOCAL_TIMEZONE)
    lunch_end = datetime.combine(day, LUNCH_END, tzinfo=LOCAL_TIMEZONE)
    return [(start, lunch_start), (lunch_end, end)]


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _build_free_windows(day: date, events: list[object]) -> list[tuple[datetime, datetime]]:
    busy = []
    day_start, day_end = _day_bounds(day)
    for event in events:
        start = _normalize_datetime(event.start_time)
        end = _normalize_datetime(event.end_time)
        if end <= day_start or start >= day_end:
            continue
        busy.append((max(start, day_start), min(end, day_end)))

    merged_busy = _merge_intervals(busy)
    windows: list[tuple[datetime, datetime]] = []
    for segment_start, segment_end in _work_segments(day):
        cursor = segment_start
        for busy_start, busy_end in merged_busy:
            if busy_end <= cursor or busy_start >= segment_end:
                continue
            if busy_start > cursor:
                windows.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if cursor < segment_end:
            windows.append((cursor, segment_end))
    return [(start, end) for start, end in windows if end > start]


def _duration_from_text(message: str, fallback: int) -> int:
    lowered = message.lower()
    if re.search(r"\b(?:for\s+)?\d+(?:\.\d+)?\s*(?:hour|hours|hr|hrs)\b", lowered) or re.search(r"\b\d+\s*(?:minute|minutes|min|mins)\b", lowered):
        return max(15, min(int(round(extract_duration_hours(message) * 60)), 240))
    return fallback


def _optimal_duration_minutes(event_type: str, priority: str, profile: CalendarProfile | None = None) -> int:
    if profile and profile.preferred_duration_minutes:
        preferred = profile.preferred_duration_minutes
    else:
        preferred = 60

    base_map = {
        "standup": 30,
        "interview": 45,
        "client": 60,
        "project": 60,
        "team_sync": 45,
        "personal": 30,
        "academic": 60,
        "ai_tech": 60,
        "urgent": 30,
    }
    base = base_map.get(event_type, preferred)
    if priority == "high":
        base = min(base, 45)
    if profile:
        base = int(round((base + preferred) / 2)) if preferred else base
    return max(15, min(base, 120))


def _preferred_hour(events: list[object]) -> int:
    if not events:
        return 10
    counter = Counter(_normalize_datetime(event.start_time).hour for event in events)
    if not counter:
        return 10
    return counter.most_common(1)[0][0]


def _preferred_duration(events: list[object]) -> int:
    durations = [max(15, int(round((_normalize_datetime(event.end_time) - _normalize_datetime(event.start_time)).total_seconds() / 60))) for event in events]
    if not durations:
        return 60
    counts = Counter(durations)
    return counts.most_common(1)[0][0]


def build_calendar_profile(events: list[object]) -> CalendarProfile:
    metadata = [
        build_display_metadata_from_event(
            title=event.title,
            start_time=_normalize_datetime(event.start_time),
            end_time=_normalize_datetime(event.end_time),
            timezone=APP_TIMEZONE,
            sync_status=getattr(event, "sync_status", "pending"),
            created_at=getattr(event, "created_at", None),
        )
        for event in events
    ]
    attendee_counter = Counter(attendee for item in metadata for attendee in item.attendees)
    pattern_counter = Counter(
        f"{item.event_type}:{_normalize_datetime(event.start_time).strftime('%A %H:%M')}"
        for item, event in zip(metadata, events)
    )

    busy_minutes = sum(
        max(0, int(round((_normalize_datetime(event.end_time) - _normalize_datetime(event.start_time)).total_seconds() / 60)))
        for event in events
    )
    working_minutes = 9 * 60 * max(1, len({(_normalize_datetime(event.start_time)).date() for event in events}) or 1)
    workload_ratio = min(1.0, busy_minutes / working_minutes) if working_minutes else 0.0
    focus_time_score = max(0, min(100, round(100 - (workload_ratio * 60) - (len(events) * 2))))

    burnout = "low"
    if workload_ratio >= 0.8 or len(events) >= 8:
        burnout = "high"
    elif workload_ratio >= 0.6 or len(events) >= 5:
        burnout = "medium"

    return CalendarProfile(
        preferred_hour=_preferred_hour(events),
        preferred_duration_minutes=_preferred_duration(events),
        frequent_attendees=[item for item, _ in attendee_counter.most_common(5)],
        recurring_patterns=[item for item, count in pattern_counter.items() if count >= 2],
        workload_ratio=round(workload_ratio, 2),
        focus_time_score=focus_time_score,
        burnout_risk=burnout,
    )


def _score_candidate(candidate_start: datetime, duration_minutes: int, profile: CalendarProfile, event_type: str, priority: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    if candidate_start.hour == profile.preferred_hour:
        score += 30
        reasons.append("matches your preferred meeting hour")
    elif abs(candidate_start.hour - profile.preferred_hour) <= 1:
        score += 18
        reasons.append("near your usual meeting hour")

    if 12 <= candidate_start.hour < 13:
        score -= 50
        reasons.append("lunch hour avoided")
    elif candidate_start.hour < 10:
        score -= 8
    elif candidate_start.hour >= 18:
        score -= 35
        reasons.append("late-night avoided")

    if event_type in {"client", "project", "ai_tech"} and 10 <= candidate_start.hour <= 16:
        score += 20
        reasons.append("best business hours")
    if event_type == "standup" and 9 <= candidate_start.hour <= 11:
        score += 20
    if priority == "high":
        score += max(0, 40 - candidate_start.hour)
        reasons.append("high priority gets earliest practical slot")

    duration_preference = max(15, min(profile.preferred_duration_minutes, 120))
    if abs(duration_minutes - duration_preference) <= 15:
        score += 12
        reasons.append("matches preferred duration")

    if event_type and profile.recurring_patterns:
        pattern_hits = [item for item in profile.recurring_patterns if item.startswith(event_type)]
        if pattern_hits:
            score += 15
            reasons.append("aligns with recurring schedule pattern")

    return score, reasons


def _candidate_slots(window_start: datetime, window_end: datetime, duration_minutes: int) -> list[datetime]:
    slots: list[datetime] = []
    cursor = window_start
    step = timedelta(minutes=SLOT_STEP_MINUTES)
    duration = timedelta(minutes=duration_minutes)
    while cursor + duration <= window_end:
        slots.append(cursor)
        cursor += step
    return slots


def _find_best_candidate_for_day(day: date, duration_minutes: int, events: list[object], profile: CalendarProfile, event_type: str, priority: str) -> tuple[datetime | None, datetime | None, list[str], str | None]:
    best_start: datetime | None = None
    best_end: datetime | None = None
    best_score = -10**9
    best_reasons: list[str] = []
    chosen_window: str | None = None

    for window_start, window_end in _build_free_windows(day, events):
        for candidate_start in _candidate_slots(window_start, window_end, duration_minutes):
            candidate_end = candidate_start + timedelta(minutes=duration_minutes)
            score, reasons = _score_candidate(candidate_start, duration_minutes, profile, event_type, priority)
            if candidate_start.hour >= 12 and candidate_start.hour < 13:
                continue
            if candidate_start.hour >= 19:
                continue
            if score > best_score:
                best_score = score
                best_start = candidate_start
                best_end = candidate_end
                best_reasons = reasons
                chosen_window = f"{candidate_start.strftime('%I:%M %p')} - {candidate_end.strftime('%I:%M %p')}"

    return best_start, best_end, best_reasons, chosen_window


def _describe_overload(events: list[object], target_date: date | None = None) -> bool:
    daily_counts = Counter(_normalize_datetime(event.start_time).date() for event in events)
    if target_date is not None and daily_counts.get(target_date, 0) >= 6:
        return True
    return any(count >= 6 for count in daily_counts.values())


def _nearest_free_slot(start_time: datetime, duration_minutes: int, events: list[object], profile: CalendarProfile, event_type: str, priority: str) -> tuple[datetime | None, datetime | None, list[str]]:
    day = start_time.date()
    for offset in range(SEARCH_WINDOW_DAYS):
        current_day = day + timedelta(days=offset)
        day_events = [event for event in events if _normalize_datetime(event.start_time).date() == current_day]
        candidate_start, candidate_end, reasons, _ = _find_best_candidate_for_day(current_day, duration_minutes, day_events, profile, event_type, priority)
        if candidate_start and candidate_end:
            if offset > 0:
                reasons.append(f"moved to nearest available slot on {candidate_start.strftime('%A')}")
            return candidate_start, candidate_end, reasons
    return None, None, []


def plan_schedule_slot(
    events: list[object],
    requested_start: datetime | None,
    requested_date: date | None,
    duration_minutes: int,
    event_type: str,
    priority: str,
    message: str,
) -> SchedulePlan:
    profile = build_calendar_profile(events)
    overloaded = _describe_overload(events, requested_date or (requested_start.date() if requested_start else None))
    recommended_duration = _optimal_duration_minutes(event_type, priority, profile)
    if duration_minutes:
        recommended_duration = min(recommended_duration, max(15, duration_minutes))
    if any(token in message.lower() for token in ["2-hour", "2 hour", "90-minute", "45-minute", "30-minute"]):
        recommended_duration = duration_minutes

    duration_minutes = max(15, recommended_duration)
    recommendations: list[str] = []
    conflict_summary: str | None = None
    reschedule_suggestion: str | None = None

    if requested_start is None and requested_date is None:
        requested_date = datetime.now(LOCAL_TIMEZONE).date()

    if requested_start is not None:
        day_events = [event for event in events if _normalize_datetime(event.start_time).date() == requested_start.date()]
        is_conflict = any(
            _normalize_datetime(event.start_time) < requested_start + timedelta(minutes=duration_minutes)
            and _normalize_datetime(event.end_time) > requested_start
            for event in day_events
        )
        if not is_conflict:
            end_time = requested_start + timedelta(minutes=duration_minutes)
            if requested_start.hour >= 12 and requested_start.hour < 13:
                recommendations.append("Lunch hour avoided")
            if requested_start.hour >= 19:
                recommendations.append("Late-night meeting avoided")
            chosen_reason = "kept your preferred time"
            if overloaded:
                recommendations.append("Your calendar is overloaded today, so keep this block focused")
            return SchedulePlan(
                start_time=requested_start,
                end_time=end_time,
                duration_minutes=duration_minutes,
                auto_planned=False,
                overloaded=overloaded,
                preferred_window=f"{requested_start.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}",
                recommendations=recommendations or ["Kept the requested time"],
                chosen_reason=chosen_reason,
            )

        suggested_start, suggested_end, reasons = _nearest_free_slot(requested_start, duration_minutes, events, profile, event_type, priority)
        if suggested_start and suggested_end:
            recommendations.extend(reasons or ["Moved to nearest free slot"])
            conflict_summary = "Requested time conflicts with an existing meeting"
            if priority == "high":
                reschedule_suggestion = f"Keep this high-priority meeting and move the conflicting item to {suggested_end.strftime('%I:%M %p')}."
            else:
                reschedule_suggestion = f"Suggested alternative slot: {suggested_start.strftime('%A %I:%M %p')}"
            return SchedulePlan(
                start_time=suggested_start,
                end_time=suggested_end,
                duration_minutes=duration_minutes,
                auto_planned=True,
                overloaded=overloaded,
                preferred_window=f"{suggested_start.strftime('%I:%M %p')} - {suggested_end.strftime('%I:%M %p')}",
                recommendations=recommendations,
                conflict_summary=conflict_summary,
                reschedule_suggestion=reschedule_suggestion,
                chosen_reason="nearest free slot chosen",
            )

    target_date = requested_date or (requested_start.date() if requested_start else datetime.now(LOCAL_TIMEZONE).date())
    for offset in range(SEARCH_WINDOW_DAYS):
        day = target_date + timedelta(days=offset)
        day_events = [event for event in events if _normalize_datetime(event.start_time).date() == day]
        candidate_start, candidate_end, reasons, window = _find_best_candidate_for_day(day, duration_minutes, day_events, profile, event_type, priority)
        if candidate_start and candidate_end:
            if offset > 0:
                recommendations.append(f"Moved to next available day: {candidate_start.strftime('%A')}")
            recommendations.extend(reasons)
            if event_type in {"client", "project", "ai_tech"} and profile.focus_time_score >= 70:
                recommendations.append("Protected focus time remains high")
            if overloaded:
                recommendations.append("Calendar is overloaded, so this was placed in the cleanest available slot")
            return SchedulePlan(
                start_time=candidate_start,
                end_time=candidate_end,
                duration_minutes=duration_minutes,
                auto_planned=True,
                overloaded=overloaded,
                preferred_window=window or f"{candidate_start.strftime('%I:%M %p')} - {candidate_end.strftime('%I:%M %p')}",
                recommendations=recommendations or ["Selected the best available slot"],
                chosen_reason="best free slot selected",
            )

    fallback_start = datetime.combine(target_date, WORKDAY_START, tzinfo=LOCAL_TIMEZONE)
    fallback_end = fallback_start + timedelta(minutes=duration_minutes)
    return SchedulePlan(
        start_time=fallback_start,
        end_time=fallback_end,
        duration_minutes=duration_minutes,
        auto_planned=True,
        overloaded=overloaded,
        preferred_window=f"{fallback_start.strftime('%I:%M %p')} - {fallback_end.strftime('%I:%M %p')}",
        recommendations=["No clean slot found, so a default workday slot was selected"],
        chosen_reason="default slot selected",
    )
