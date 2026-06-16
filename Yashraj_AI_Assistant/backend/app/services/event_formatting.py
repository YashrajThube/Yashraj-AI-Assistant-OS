from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from app.core.config import APP_TIMEZONE
from app.services.intent_service import strip_datetime_phrases

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
_ACRONYMS = {"ai", "api", "ui", "ux", "llm", "ml", "sql", "oauth", "db", "pm", "qa", "tcs", "ibm", "hcl", "wipro"}
_LOWERCASE_WORDS = {"a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with", "vs"}
_TITLE_BOUNDARY_WORDS = {
    "call",
    "discussion",
    "meeting",
    "project",
    "review",
    "session",
    "sync",
    "test",
    "testing",
    "work",
}
_MEANINGFUL_TITLE_WORDS = {
    "academic",
    "call",
    "client",
    "discussion",
    "interview",
    "meeting",
    "project",
    "review",
    "session",
    "sync",
    "team",
    "urgent",
    "work",
}
_EVENT_TYPE_KEYWORDS = {
    "interview": {"interview", "screening", "round", "hr round", "technical round"},
    "client": {"client", "customer", "vendor", "partner", "account"},
    "personal": {"doctor", "dentist", "gym", "family", "personal", "birthday", "lunch", "appointment"},
    "academic": {"college", "school", "lecture", "presentation", "seminar", "academic", "class", "assignment"},
    "standup": {"standup", "daily standup", "scrum"},
    "team_sync": {"team sync", "sync", "catchup", "catch-up", "team meeting"},
    "project": {"project", "roadmap", "architecture", "planning", "design", "discussion", "review"},
    "ai_tech": {"ai", "architecture", "engineering", "technical", "tech", "planning", "design"},
    "urgent": {"urgent", "asap", "critical", "important", "high priority"},
    "meeting": {"meeting", "call", "session"},
}
_PRIORITY_KEYWORDS = {
    "high": {"urgent", "important", "high priority", "critical", "asap", "immediately", "priority"},
    "normal": set(),
}
_EVENT_PRIORITY_ORDER = ["urgent", "interview", "client", "academic", "standup", "team_sync", "project", "personal", "meeting", "general"]


@dataclass(slots=True)
class ScheduleMetadata:
    original_prompt: str
    title: str
    description: str
    attendees: list[str]
    timezone: str
    event_type: str
    priority: str
    confidence: float
    parsed_datetime: datetime | None
    duration_minutes: int
    color_id: str
    duplicate_risk: str = "low"
    agenda_items: list[str] | None = None
    prep_notes: list[str] | None = None
    sync_status: str = "pending"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _smart_title_case(text: str) -> str:
    parts = re.split(r"([\s\-/:,]+)", text)
    normalized: list[str] = []
    seen_word = False
    for part in parts:
        if not part or re.fullmatch(r"[\s\-/:,]+", part):
            normalized.append(part)
            continue
        lowered = part.lower()
        if lowered in _ACRONYMS:
            normalized.append(lowered.upper())
            seen_word = True
            continue
        if lowered in _LOWERCASE_WORDS and seen_word:
            normalized.append(lowered)
            seen_word = True
            continue
        normalized.append(lowered[:1].upper() + lowered[1:])
        seen_word = True
    return _normalize_whitespace("".join(normalized))


def _extract_attendees(text: str) -> list[str]:
    lowered = text.lower()
    match = re.search(r"\bwith\s+(.+)$", lowered)
    if not match:
        return []

    tail = match.group(1)
    tail = re.split(r"\b(?:for|on|at|to|tomorrow|today|next week|next month|morning|afternoon|evening)\b", tail, maxsplit=1)[0]
    words = tail.split()
    trimmed_words = []
    for word in words:
        if re.sub(r"[^\w&.-]", "", word).lower() in _TITLE_BOUNDARY_WORDS:
            break
        trimmed_words.append(word)
    tail = " ".join(trimmed_words)
    tail = re.sub(r"\b(?:meeting|call|sync|session|discussion|planning|plan|project|team)\b", "", tail)
    raw_names = re.split(r"\b(?:and|with|&|,|/|plus)\b", tail)
    attendees: list[str] = []
    for item in raw_names:
        candidate = _normalize_whitespace(item)
        if not candidate:
            continue
        candidate = candidate.strip(" .-_")
        if not candidate or len(candidate) < 2:
            continue
        if candidate in {"me", "us", "team", "someone", "someone else", "others"}:
            continue
        attendees.append(_smart_title_case(candidate))

    deduped: list[str] = []
    for attendee in attendees:
        if attendee not in deduped:
            deduped.append(attendee)
    return deduped


def _extract_attendees_from_title(title: str) -> list[str]:
    match = re.search(r"\bwith\s+(.+)$", title, flags=re.IGNORECASE)
    if not match:
        return []
    tail = re.split(r"\b(?:and|&|,|/|plus|for|on|at|to)\b", match.group(1), maxsplit=1)[0]
    words = tail.split()
    trimmed_words = []
    for word in words:
        if re.sub(r"[^\w&.-]", "", word).lower() in _TITLE_BOUNDARY_WORDS:
            break
        trimmed_words.append(word)
    tail = " ".join(trimmed_words)
    raw_names = re.split(r"\b(?:and|&|,|/|plus)\b", tail)
    attendees: list[str] = []
    for item in raw_names:
        candidate = _normalize_whitespace(item).strip(" .-_")
        if candidate:
            attendees.append(_smart_title_case(candidate))
    deduped: list[str] = []
    for attendee in attendees:
        if attendee not in deduped:
            deduped.append(attendee)
    return deduped


def _event_type_for_text(text: str, attendees: list[str]) -> str:
    lowered = text.lower()
    if lowered.strip() == "team":
        return "team_sync"
    if "testing" in lowered or re.search(r"\btest\b", lowered):
        return "project"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["urgent"]):
        return "urgent"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["interview"]):
        return "interview"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["client"]):
        return "client"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["personal"]):
        return "personal"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["academic"]):
        return "academic"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["standup"]):
        return "standup"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["team_sync"]):
        return "team_sync"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["project"]):
        return "project"
    if any(token in lowered for token in _EVENT_TYPE_KEYWORDS["ai_tech"]):
        return "ai_tech"
    if attendees or any(token in lowered for token in _EVENT_TYPE_KEYWORDS["meeting"]):
        return "meeting"
    return "general"


def _priority_for_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in _PRIORITY_KEYWORDS["high"]):
        return "high"
    return "normal"


def _duplicate_risk_for(title: str, attendees: list[str], priority: str) -> str:
    if priority == "high":
        return "medium"
    if attendees and title:
        return "medium"
    return "low"


def _color_for_event_type(event_type: str, priority: str) -> str:
    if priority == "high":
        return "11"
    mapping = {
        "interview": "9",
        "client": "10",
        "personal": "5",
        "academic": "3",
        "standup": "8",
        "team_sync": "8",
        "project": "7",
        "ai_tech": "3",
        "meeting": "9",
    }
    return mapping.get(event_type, "9")


def _agenda_items_for(event_type: str, priority: str) -> list[str]:
    agenda_map = {
        "interview": ["Candidate introduction", "Technical evaluation", "Q&A and next steps"],
        "client": ["Project discussion", "Timeline review", "Action items"],
        "personal": ["Appointment details", "Required preparation", "Follow-up plan"],
        "academic": ["Topic overview", "Presentation", "Questions and feedback"],
        "standup": ["Yesterday's progress", "Today's priorities", "Blockers"],
        "team_sync": ["Status updates", "Dependencies", "Decision points"],
        "project": ["Scope review", "Milestones", "Risks and actions"],
        "urgent": ["Immediate issue review", "Decisions", "Ownership and next action"],
        "ai_tech": ["Architecture review", "Technical decisions", "Implementation plan"],
    }
    agenda = agenda_map.get(event_type, ["Discussion", "Decisions", "Action items"])
    if priority == "high":
        return ["Priority confirmation", *agenda[:2], "Immediate action items"]
    return agenda


def _prep_notes_for(event_type: str, priority: str, attendees: list[str]) -> list[str]:
    notes = []
    if attendees:
        notes.append("Confirm attendee availability")
    if event_type in {"client", "project", "ai_tech"}:
        notes.append("Prepare status updates and open questions")
    if event_type == "interview":
        notes.append("Review role requirements and candidate background")
    if priority == "high":
        notes.append("Block immediate follow-up time")
    return notes or ["Review the context and arrive prepared"]


def _dedupe_consecutive_words(text: str) -> str:
    words = text.split()
    deduped: list[str] = []
    for word in words:
        if deduped and deduped[-1].lower() == word.lower():
            continue
        deduped.append(word)
    return " ".join(deduped)


def _format_duration_label(duration_minutes: int) -> str:
    total_minutes = max(1, int(duration_minutes))
    if total_minutes % 60 == 0:
        hours = total_minutes // 60
        return f"{hours} Hour" if hours == 1 else f"{hours} Hours"
    return f"{total_minutes} Minutes" if total_minutes != 1 else "1 Minute"


def _build_structured_calendar_description(
    *,
    event_type: str,
    priority: str,
    attendees: list[str],
    duration_minutes: int,
    timezone: str,
    status: str | None = None,
    notes: str | None = None,
) -> str:
    agenda_items = _agenda_items_for(event_type, priority)
    description_lines = [
        "Meeting Type:",
        event_type_label(event_type),
        "",
        "Attendees:",
        ", ".join(attendees) if attendees else "None",
        "",
        "Agenda:",
        "; ".join(agenda_items) if agenda_items else "AI-generated scheduling discussion",
        "",
        "Duration:",
        _format_duration_label(duration_minutes),
        "",
        "Timezone:",
        timezone or APP_TIMEZONE,
        "",
        "Generated By:",
        "Yashraj AI Assistant OS",
    ]
    if status:
        description_lines.extend(["", "Status:", status])
    if notes:
        description_lines.extend(["", "Manual Notes:", notes.strip()])
    return "\n".join(description_lines)


def priority_label(priority: str) -> str:
    return "High Priority" if priority == "high" else "Normal"


def event_type_label(event_type: str) -> str:
    labels = {
        "interview": "Interview",
        "client": "Client Meeting",
        "personal": "Personal Appointment",
        "academic": "Academic",
        "standup": "Standup",
        "team_sync": "Team Sync",
        "project": "Project Discussion",
        "urgent": "Urgent",
        "ai_tech": "AI / Tech",
        "meeting": "Meeting",
        "general": "General",
    }
    return labels.get(event_type, "General")


def _subject_from_text(text: str) -> str:
    cleaned = strip_datetime_phrases(text)
    cleaned = re.sub(r"\b(?:please|pls|kindly)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:schedule|create|set|arrange|book|reminder for)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:a|an|the)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:with|for|on|at|from|to|in|of)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s&\-/]+", " ", cleaned)
    return _normalize_whitespace(cleaned)


def _build_title(subject: str, attendees: list[str], event_type: str) -> str:
    attendee_label = " and ".join(attendees) if attendees else ""
    subject = _smart_title_case(subject) if subject else ""
    lowered_subject = subject.lower()

    if attendees and subject:
        subject_words = subject
        for attendee in attendees:
            pieces = [re.escape(part) for part in attendee.split() if part]
            if not pieces:
                continue
            subject_words = re.sub(rf"\b{pieces[0]}\b", "", subject_words, flags=re.IGNORECASE)
            if len(pieces) > 1:
                subject_words = re.sub(rf"\b{pieces[0]}\s+{pieces[-1]}\b", "", subject_words, flags=re.IGNORECASE)
        subject = _normalize_whitespace(subject_words)

    if event_type == "interview":
        if attendee_label:
            if attendee_label.isupper() or len(attendee_label.split()) == 1:
                return f"{attendee_label} Interview Session"
            return f"Interview with {attendee_label}"
        return "Interview Session"

    if event_type == "client":
        client_name = subject or attendee_label or "Client"
        client_name = re.sub(r"\b(?:Client|Meeting|Call|Session|Planning|Discussion|Sync)\b", "", client_name, flags=re.IGNORECASE)
        client_name = _normalize_whitespace(client_name) or "Client"
        if "call" in lowered_subject:
            return f"Client Call - {_smart_title_case(client_name)}"
        return f"Client Meeting - {_smart_title_case(client_name)}"

    if event_type == "standup":
        return "Standup"

    if event_type == "team_sync":
        return "Team Sync Meeting"

    if event_type == "personal":
        return "Personal Appointment"

    if event_type == "academic":
        if "presentation" in lowered_subject:
            return "Academic Presentation"
        if "lecture" in lowered_subject or "class" in lowered_subject:
            return "Academic Session"
        return "Academic Event"

    if event_type == "project":
        return f"Project Discussion with {attendee_label}" if attendee_label else "Project Discussion"

    if event_type == "urgent":
        return "Urgent Meeting"

    if event_type == "ai_tech":
        core = subject or attendee_label or "AI Architecture Planning"
        core = re.sub(r"\b(?:Meeting|Call|Session)\b", "", core, flags=re.IGNORECASE)
        core = _normalize_whitespace(core) or "AI Architecture Planning"
        if not re.search(r"\b(session|meeting|call)$", core, flags=re.IGNORECASE):
            core = f"{core} Session"
        return _smart_title_case(core)

    if attendee_label:
        if subject:
            subject = re.sub(r"\b(?:Meeting|Call|Session|Sync)\b", "", subject, flags=re.IGNORECASE)
            subject = _normalize_whitespace(subject)
            normalized_subject = subject.lower()
            if (
                not subject
                or normalized_subject == attendee_label.lower()
                or normalized_subject.startswith("with ")
                or normalized_subject.endswith(" with")
                or normalized_subject in {"now", "meeting", "call", "session", "sync"}
            ):
                return f"Meeting with {attendee_label}"
        return f"{_smart_title_case(subject)} with {attendee_label}"

    if event_type == "meeting":
        core = subject or "Meeting"
        if not re.search(r"\b(meeting|session|call)$", core, flags=re.IGNORECASE):
            core = f"{core} Meeting"
        return _smart_title_case(core)

    if subject:
        return _smart_title_case(subject)
    return "Meeting"


def _confidence_score(attendees: list[str], subject: str, event_type: str) -> float:
    score = 0.55
    if attendees:
        score += 0.15
    if subject:
        score += 0.15
    if event_type != "general":
        score += 0.1
    if any(token in subject.lower() for token in ["planning", "discussion", "meeting", "sync", "call"]):
        score += 0.05
    return min(round(score, 2), 0.99)


def build_schedule_metadata(
    original_prompt: str,
    parsed_datetime: datetime | None,
    duration_minutes: int,
    timezone: str | None = None,
) -> ScheduleMetadata:
    prompt = _normalize_whitespace(original_prompt)
    attendees = _extract_attendees(prompt)
    subject = _subject_from_text(prompt)
    event_type = _event_type_for_text(prompt, attendees)
    priority = _priority_for_text(prompt)
    title = _build_title(subject=subject, attendees=attendees, event_type=event_type)
    title = _normalize_whitespace(title)
    if not title or title.lower() == title:
        title = "Meeting"

    if len(title) > 255:
        title = title[:255].rstrip()

    if not timezone:
        timezone = APP_TIMEZONE

    color_id = _color_for_event_type(event_type, priority)
    description = _build_structured_calendar_description(
        event_type=event_type,
        priority=priority,
        attendees=attendees,
        duration_minutes=duration_minutes,
        timezone=timezone,
        status="Pending Google Sync",
    )

    return ScheduleMetadata(
        original_prompt=prompt,
        title=title,
        description=description,
        attendees=attendees,
        timezone=timezone,
        event_type=event_type,
        priority=priority,
        confidence=_confidence_score(attendees, subject, event_type),
        parsed_datetime=parsed_datetime,
        duration_minutes=duration_minutes,
        color_id=color_id,
        duplicate_risk=_duplicate_risk_for(title, attendees, priority),
        agenda_items=_agenda_items_for(event_type, priority),
        prep_notes=_prep_notes_for(event_type, priority, attendees),
    )


def build_display_metadata_from_event(
    title: str,
    start_time: datetime,
    end_time: datetime,
    timezone: str | None = None,
    sync_status: str = "pending",
    created_at: datetime | None = None,
    notes: str | None = None,
) -> ScheduleMetadata:
    normalized_title = ensure_professional_title(title)
    attendees = _extract_attendees_from_title(normalized_title)
    event_type = _event_type_for_text(normalized_title, attendees)
    priority = _priority_for_text(normalized_title)
    if timezone is None:
        timezone = APP_TIMEZONE
    if created_at is None:
        created_at = datetime.now(dt_timezone.utc)
    color_id = _color_for_event_type(event_type, priority)
    description = _build_structured_calendar_description(
        event_type=event_type,
        priority=priority,
        attendees=attendees,
        duration_minutes=max(1, int(round((end_time - start_time).total_seconds() / 60))),
        timezone=timezone,
        status="Synced with Google Calendar" if sync_status == "synced" else "Pending Google Sync",
        notes=notes,
    )

    return ScheduleMetadata(
        original_prompt=normalized_title,
        title=normalized_title,
        description=description,
        attendees=attendees,
        timezone=timezone,
        event_type=event_type,
        priority=priority,
        confidence=0.9,
        parsed_datetime=start_time,
        duration_minutes=max(1, int(round((end_time - start_time).total_seconds() / 60))),
        color_id=color_id,
        duplicate_risk=_duplicate_risk_for(normalized_title, attendees, priority),
        agenda_items=_agenda_items_for(event_type, priority),
        prep_notes=_prep_notes_for(event_type, priority, attendees),
        sync_status=sync_status,
    )


def _ensure_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.isoformat()


def color_id_for_event_type(event_type: str) -> str:
    return _color_for_event_type(event_type, "high" if event_type == "urgent" else "normal")


def ensure_professional_title(title: str) -> str:
    cleaned = _normalize_whitespace(title)
    cleaned = re.sub(r"\b(?:schedule|create|set|arrange|book|reminder for)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:now|please|pls|kindly|just|a|an|the)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:am|pm)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:at|from|to|for)\s*(?:\d{1,2}(?::\d{2})?|\d{1,2}\s+\d{2})(?:\s*(?:am|pm))?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:for\s+)?\d+\s*(?:hour|hours|hr|hrs|minute|minutes|min|mins)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}\s+\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:hour|hours|hr|hrs|minute|minutes|min|mins)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    if not cleaned:
        return "Meeting"

    lowered = cleaned.lower()
    if lowered == "team":
        return "Team Collaboration Meeting"

    if "testing" in lowered or re.search(r"\btest\b", lowered):
        return "Project Testing Session"

    if lowered.startswith("with "):
        attendee = _normalize_whitespace(cleaned[5:])
        attendee = re.split(r"\b(?:for|on|at|to|tomorrow|today|next week|next month|morning|afternoon|evening)\b", attendee, maxsplit=1)[0]
        attendee = _normalize_whitespace(attendee)
        return f"Meeting with {_smart_title_case(attendee)}" if attendee else "Meeting"

    if "client" in lowered and "call" in lowered and "-" not in cleaned:
        return "Client Strategy Call"

    if lowered in {"meeting", "call", "session", "discussion", "sync"}:
        return "Project Discussion Meeting"

    if lowered.startswith("meeting with "):
        attendee = _normalize_whitespace(cleaned[len("meeting with "):])
        attendee = re.split(r"\b(?:for|on|at|to|tomorrow|today|next week|next month|morning|afternoon|evening)\b", attendee, maxsplit=1)[0]
        attendee = _normalize_whitespace(attendee)
        return f"Meeting with {_smart_title_case(attendee)}" if attendee else "Meeting"

    if lowered.startswith("call with "):
        attendee = _normalize_whitespace(cleaned[len("call with "):])
        attendee = re.split(r"\b(?:for|on|at|to|tomorrow|today|next week|next month|morning|afternoon|evening)\b", attendee, maxsplit=1)[0]
        attendee = _normalize_whitespace(attendee)
        return f"Call with {_smart_title_case(attendee)}" if attendee else "Call"

    if " with " in lowered:
        prefix = lowered.split(" with ", 1)[0]
        prefix_words = {word for word in re.findall(r"[a-z]+", prefix) if word}
        if not prefix_words.intersection(_MEANINGFUL_TITLE_WORDS):
            attendee = _normalize_whitespace(cleaned.split(" with ", 1)[1])
            if attendee:
                attendee = re.split(r"\b(?:for|on|at|to|tomorrow|today|next week|next month|morning|afternoon|evening)\b", attendee, maxsplit=1)[0]
                attendee = _normalize_whitespace(attendee)
                if attendee:
                    return f"Meeting with {_smart_title_case(attendee)}"

    attendees = _extract_attendees_from_title(cleaned)
    attendees = [_dedupe_consecutive_words(attendee) for attendee in attendees]
    event_type = _event_type_for_text(cleaned, attendees)
    subject = _subject_from_text(cleaned)
    subject_core = _normalize_whitespace(subject).lower()
    if attendees and subject_core and len(subject_core.split()) == 1 and subject_core not in {
        "client",
        "call",
        "discussion",
        "meeting",
        "project",
        "review",
        "session",
        "sync",
        "team",
        "work",
    }:
        return f"Meeting with {_smart_title_case(' and '.join(attendees))}"

    professional = _build_title(subject=subject, attendees=attendees, event_type=event_type)
    professional = _normalize_whitespace(professional)
    return professional if professional else "Meeting"
