from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.event_formatting import ScheduleMetadata, event_type_label, priority_label


@dataclass(slots=True)
class AssistantTemplate:
    title: str
    body: str
    subject: str | None = None
    action_type: str = "template"


def _join_bullets(items: list[str]) -> str:
    return "\n".join([f"- {item}" for item in items]) if items else "- None"


def build_meeting_invite_email(metadata: ScheduleMetadata) -> AssistantTemplate:
    attendees = ", ".join(metadata.attendees) if metadata.attendees else "the team"
    subject = f"Invitation: {metadata.title}"
    body = (
        f"Hi {attendees},\n\n"
        f"You are invited to {metadata.title} on {metadata.parsed_datetime.strftime('%A, %d %B %Y at %I:%M %p') if metadata.parsed_datetime else 'the scheduled time'}.\n"
        f"Event type: {event_type_label(metadata.event_type)}\n"
        f"Priority: {priority_label(metadata.priority)}\n\n"
        f"Agenda:\n{_join_bullets(metadata.agenda_items or [])}\n\n"
        f"Preparation checklist:\n{_join_bullets(metadata.prep_notes or [])}\n\n"
        "Please confirm your availability.\n\nBest,\nYashraj AI Assistant"
    )
    return AssistantTemplate(title="Meeting invitation email", body=body, subject=subject, action_type="email")


def build_follow_up_summary(metadata: ScheduleMetadata, notes: list[str] | None = None) -> AssistantTemplate:
    summary_lines = [
        f"Summary for {metadata.title}",
        f"Type: {event_type_label(metadata.event_type)}",
        f"Priority: {priority_label(metadata.priority)}",
        "",
        "Action items:",
        _join_bullets(notes or metadata.agenda_items or []),
    ]
    return AssistantTemplate(title="Follow-up summary", body="\n".join(summary_lines), action_type="follow_up")


def build_action_items(metadata: ScheduleMetadata) -> AssistantTemplate:
    items = metadata.agenda_items or ["Confirm next steps", "Assign owners", "Set follow-up time"]
    return AssistantTemplate(title="Action items", body=_join_bullets(items), action_type="action_items")


def build_reminder_message(metadata: ScheduleMetadata, minutes_before: int = 30) -> AssistantTemplate:
    reminder_time = f"{minutes_before} minutes"
    body = (
        f"Reminder: {metadata.title} starts in {reminder_time}.\n"
        f"Priority: {priority_label(metadata.priority)}\n"
        f"Agenda focus: {metadata.agenda_items[0] if metadata.agenda_items else 'Review the key objectives'}"
    )
    return AssistantTemplate(title="Reminder message", body=body, action_type="reminder")


def build_prep_checklist(metadata: ScheduleMetadata) -> AssistantTemplate:
    items = metadata.prep_notes or ["Review the meeting context", "Prepare questions", "Confirm materials"]
    return AssistantTemplate(title="Preparation checklist", body=_join_bullets(items), action_type="checklist")


def build_email_summary_from_prompt(message: str) -> AssistantTemplate:
    subject = "Meeting follow-up draft"
    body = (
        "Hi team,\n\n"
        f"Sharing a concise follow-up for: {message.strip()}\n\n"
        "Key points:\n- Confirm decisions\n- Assign owners\n- Track deadlines\n\n"
        "Best,\nYashraj AI Assistant"
    )
    return AssistantTemplate(title="Generic email draft", body=body, subject=subject, action_type="email")


def build_template_response(message: str, metadata: ScheduleMetadata | None = None) -> AssistantTemplate:
    lowered = message.lower()
    if metadata and any(token in lowered for token in ["invite email", "meeting email", "email invite", "draft email"]):
        return build_meeting_invite_email(metadata)
    if metadata and any(token in lowered for token in ["follow up", "follow-up", "summary", "recap"]):
        return build_follow_up_summary(metadata)
    if metadata and any(token in lowered for token in ["action items", "next steps"]):
        return build_action_items(metadata)
    if metadata and any(token in lowered for token in ["reminder", "notify me"]):
        return build_reminder_message(metadata)
    if metadata and any(token in lowered for token in ["checklist", "prep"]):
        return build_prep_checklist(metadata)
    return build_email_summary_from_prompt(message)
