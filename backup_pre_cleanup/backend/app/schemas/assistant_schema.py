from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class ScheduledEventOut(BaseModel):
    id: int
    user_id: int
    title: str
    start_time: datetime
    end_time: datetime


class ChatResponse(BaseModel):
    success: bool
    intent: Literal["schedule", "delete_event", "note", "email", "follow_up", "action_items", "reminder", "checklist", "insights", "chat", "multi"]
    response: str
    event: ScheduledEventOut | None = None
    deleted: int | None = None
