from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CalendarCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_event_window(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be empty")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEventOut(BaseModel):
    id: int
    user_id: int
    title: str
    start_time: datetime
    end_time: datetime
    google_event_id: str | None = None
    sync_status: str
    sync_error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarCleanupRequest(BaseModel):
    action: Literal["delete", "shift"]
    before_date: date | None = None
    event_ids: list[int] = Field(default_factory=list)
    shift_minutes: int = 0

    @model_validator(mode="after")
    def validate_cleanup_request(self):
        if not self.event_ids and self.before_date is None:
            raise ValueError("before_date or event_ids is required")
        if self.action == "shift" and self.shift_minutes == 0:
            raise ValueError("shift_minutes must be non-zero when action is shift")
        return self


class CalendarCleanupResponse(BaseModel):
    success: bool
    action: Literal["delete", "shift"]
    matched: int
    affected: int
    event_ids: list[int]
