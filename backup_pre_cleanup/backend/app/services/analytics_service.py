from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_TIMEZONE
from app.models.event_model import Event
from app.models.failed_job_model import FailedJob
from app.services.analytics_cache import get_cached_analytics, set_cached_analytics
from app.services.event_formatting import build_display_metadata_from_event
from app.services.scheduling_intelligence_service import build_calendar_profile


async def build_dashboard_analytics(db: AsyncSession, user_id: int) -> dict:
    cached = get_cached_analytics(user_id)
    if cached is not None:
        return cached

    events = list((await db.scalars(select(Event).where(Event.user_id == user_id))).all())
    failed_job_rows = (await db.execute(select(FailedJob.status, func.count()).group_by(FailedJob.status))).all()

    derived = [
        build_display_metadata_from_event(
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            timezone=APP_TIMEZONE,
            sync_status=event.sync_status,
            created_at=event.created_at,
        )
        for event in events
    ]

    total_meetings = len(events)
    category_counts = Counter(item.event_type for item in derived)
    priority_counts = Counter(item.priority for item in derived)
    sync_counts = Counter(getattr(event, "sync_status", "pending") for event in events)
    profile = build_calendar_profile(events)

    per_day = defaultdict(int)
    per_weekday = Counter()
    for event in events:
        start = event.start_time
        if start.tzinfo is not None:
            start = start.astimezone(start.tzinfo)
        per_day[start.date().isoformat()] += 1
        per_weekday[start.strftime("%A")] += 1

    busiest_day = None
    if per_day:
        busiest_day = max(per_day.items(), key=lambda item: item[1])[0]

    working_minutes = 9 * 60
    used_minutes = 0
    for event in events:
        start = event.start_time
        end = event.end_time
        used_minutes += max(0, int((end - start).total_seconds() // 60))

    free_time_minutes = max(0, working_minutes * max(1, len(per_day) or 1) - used_minutes)
    productivity_score = min(100, max(0, 45 + total_meetings * 3 + category_counts.get("project", 0) * 5 + priority_counts.get("high", 0) * 4 - len([e for e in events if getattr(e, "sync_status", "") != "synced"]) * 2))
    sync_health = round((sync_counts.get("synced", 0) / total_meetings) * 100, 1) if total_meetings else 100.0
    focus_time_score = profile.focus_time_score
    overload_score = min(100, max(0, round(profile.workload_ratio * 100)))
    burnout_risk = profile.burnout_risk
    category_trends = [
        {"category": key, "count": value, "share": round((value / total_meetings) * 100, 1) if total_meetings else 0}
        for key, value in category_counts.most_common()
    ]
    weekly_insights = [
        f"You had {total_meetings} meetings in total.",
        f"{round((category_counts.get('client', 0) / total_meetings) * 100, 1) if total_meetings else 0}% were client-related." if total_meetings else "No client meetings recorded.",
        f"Focus-time score is {focus_time_score}/100.",
    ]
    smart_recommendations = [
        "Protect at least one lunch-free focus block each day.",
        "Keep high-priority meetings in the morning when possible.",
        "Batch client meetings on your busiest collaboration day.",
    ]
    if burnout_risk == "high":
        smart_recommendations.insert(0, "Reduce meeting load and add recovery time between sessions.")
    elif burnout_risk == "medium":
        smart_recommendations.insert(0, "Watch for meeting clustering and preserve a deep-work block.")
    retry_stats = {status: 0 for status in ("pending", "retrying", "failed", "completed")}
    for status, count in failed_job_rows:
        retry_stats[status] = int(count)

    analytics = {
        "total_meetings": total_meetings,
        "meeting_categories": dict(category_counts),
        "productivity_score": productivity_score,
        "busiest_day": busiest_day,
        "free_time_analysis": {
            "estimated_free_minutes": free_time_minutes,
            "working_minutes_per_day": working_minutes,
        },
        "priority_distribution": dict(priority_counts),
        "sync_health": {
            "synced": sync_counts.get("synced", 0),
            "pending": sync_counts.get("pending", 0),
            "retry_pending": sync_counts.get("retry_pending", 0),
            "score": sync_health,
        },
        "retry_statistics": retry_stats,
        "heatmap": dict(per_day),
        "executive_insights": {
            "burnout_risk": burnout_risk,
            "focus_time_score": focus_time_score,
            "meeting_overload_score": overload_score,
            "preferred_meeting_hour": profile.preferred_hour,
            "preferred_duration_minutes": profile.preferred_duration_minutes,
            "frequent_attendees": profile.frequent_attendees,
            "recurring_patterns": profile.recurring_patterns,
            "workload_ratio": profile.workload_ratio,
            "weekly_summary": weekly_insights[0] if weekly_insights else "No weekly summary available.",
            "weekly_insights": weekly_insights,
            "smart_recommendations": smart_recommendations,
            "category_trends": category_trends,
            "weekday_distribution": dict(per_weekday),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    set_cached_analytics(user_id, analytics)
    return analytics