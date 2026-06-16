import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.analytics_service import build_dashboard_analytics


class AnalyticsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class AnalyticsSession:
    def __init__(self, events, failed_jobs):
        self.events = events
        self.failed_jobs = failed_jobs

    async def scalars(self, statement):
        text = str(statement)
        return AnalyticsResult(self.events)

    async def execute(self, statement):
        text = str(statement)
        if "failed_jobs" in text:
            counts = {}
            for job in self.failed_jobs:
                counts[job.status] = counts.get(job.status, 0) + 1
            return AnalyticsResult(list(counts.items()))
        return AnalyticsResult([])


def test_build_dashboard_analytics_summarizes_events(monkeypatch):
    events = [
        SimpleNamespace(
            title="Project Sync",
            start_time=datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 25, 11, 0, tzinfo=timezone.utc),
            sync_status="synced",
            created_at=datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            title="Client Review",
            start_time=datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 25, 12, 30, tzinfo=timezone.utc),
            sync_status="pending",
            created_at=datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc),
        ),
    ]
    failed_jobs = [SimpleNamespace(status="pending"), SimpleNamespace(status="completed")]

    def fake_display_metadata_from_event(**kwargs):
        return SimpleNamespace(event_type="project" if kwargs["title"] == "Project Sync" else "client", priority="high" if kwargs["title"] == "Client Review" else "normal")

    monkeypatch.setattr("app.services.analytics_service.build_display_metadata_from_event", fake_display_metadata_from_event)

    analytics = asyncio.run(build_dashboard_analytics(AnalyticsSession(events, failed_jobs), 1))

    assert analytics["total_meetings"] == 2
    assert analytics["meeting_categories"]["project"] == 1
    assert analytics["meeting_categories"]["client"] == 1
    assert analytics["priority_distribution"]["high"] == 1
    assert analytics["sync_health"]["synced"] == 1
    assert analytics["retry_statistics"]["pending"] == 1
    assert analytics["executive_insights"]["focus_time_score"] >= 0
    assert analytics["executive_insights"]["burnout_risk"] in {"low", "medium", "high"}
