import asyncio
import json
import logging
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import requests
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import GEMINI_MODEL, GEMINI_MODEL_CANDIDATES, GEMINI_TEMPERATURE, GOOGLE_API_KEY, LLM_TIMEOUT_SECONDS
from app.monitoring.metrics import incr
from app.services.event_formatting import ScheduleMetadata, build_schedule_metadata

logger = logging.getLogger(__name__)
_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_QUOTA_COOLDOWN_REQUESTS = 3
_quota_cooldown_remaining_requests = 0
GEMINI_MAX_RETRIES = 3
GEMINI_BACKOFF_BASE = 1.5

SYSTEM_PROMPT = (
    "You are an AI assistant that extracts structured actions from user input.\n"
    "Always return valid JSON.\n"
    "Do not return text outside JSON.\n"
    "Supported intents:\n"
    "- schedule\n"
    "- delete_event\n"
    "- note\n"
    "- email\n"
    "- follow_up\n"
    "- action_items\n"
    "- reminder\n"
    "- checklist\n"
    "- insights\n"
    "- chat"
)

INTENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intents": {
            "type": "array",
            "items": {"type": "string", "enum": ["schedule", "delete_event", "note", "email", "follow_up", "action_items", "reminder", "checklist", "insights", "chat"]},
            "minItems": 1,
        },
        "data": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "datetime": {"type": "string"},
                "duration": {"type": "string"},
                "note": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["intents", "data"],
    "additionalProperties": False,
}

SCHEDULE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "duration_minutes": {"type": "number"},
        "attendees": {"type": "array", "items": {"type": "string"}},
        "timezone": {"type": "string"},
        "event_type": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["title", "description", "start_time", "end_time", "duration_minutes", "attendees", "timezone", "event_type", "confidence"],
    "additionalProperties": False,
}


def _is_non_retryable_gemini_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in [
            "not_found",          # invalid model
            "resource_exhausted", # quota
            "quota exceeded",
            "quota",
            "429",
            "404",
            "api key expired",
            "api_key_invalid",
            "invalid_argument",
        ]
    )


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "quota" in text or "resource_exhausted" in text


def _is_invalid_model_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "404" in text or "not_found" in text


def _is_quota_cooldown_active() -> bool:
    return _quota_cooldown_remaining_requests > 0


def _start_quota_cooldown() -> None:
    global _quota_cooldown_remaining_requests
    _quota_cooldown_remaining_requests = _QUOTA_COOLDOWN_REQUESTS


def _consume_quota_cooldown_request() -> None:
    global _quota_cooldown_remaining_requests
    if _quota_cooldown_remaining_requests > 0:
        _quota_cooldown_remaining_requests -= 1


def _log_gemini_event(status: str, model_name: str, response_time_ms: float, error: str | None = None) -> None:
    payload: dict[str, Any] = {
        "event": "gemini_call",
        "status": status,
        "model": model_name,
        "response_time_ms": round(response_time_ms, 2),
    }
    if error:
        payload["error"] = error
    logger.info(json.dumps(payload, ensure_ascii=True))


def _extract_json_blob(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        return match.group(0)

    raise ValueError("No JSON object found in Gemini response")


def _parse_json_with_cleanup_retry(raw: str) -> dict[str, Any]:
    first_error: Exception | None = None
    for attempt in range(2):
        try:
            candidate = _extract_json_blob(raw)
            return json.loads(candidate)
        except Exception as exc:
            if first_error is None:
                first_error = exc
            if attempt == 0:
                # Retry once after cleaning common malformed JSON artifacts.
                raw = re.sub(r"```(?:json)?|```", "", raw, flags=re.IGNORECASE).strip()
                raw = re.sub(r",\s*([}\]])", r"\1", raw)
                continue
            raise ValueError(f"Gemini returned invalid JSON: {exc}") from first_error
    raise ValueError("Gemini returned invalid JSON")


def _call_gemini_rest_sync(model_name: str, system_prompt: str, user_prompt: str) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY missing")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GOOGLE_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
        "generationConfig": {
            "temperature": GEMINI_TEMPERATURE,
            "maxOutputTokens": 96,
        },
    }
    started = time.perf_counter()
    response = requests.post(url, json=payload, timeout=LLM_TIMEOUT_SECONDS)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        # Count quota (429) events for monitoring
        if response.status_code == 429:
            incr("gemini_429")
        _log_gemini_event(status="fail", model_name=model_name, response_time_ms=elapsed_ms, error=response.text[:300])
        raise RuntimeError(f"Gemini REST error ({response.status_code}): {response.text[:300]}")

    data = response.json()
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
        .strip()
    )
    if not text:
        raise RuntimeError("Gemini REST returned empty text")

    _log_gemini_event(status="success", model_name=model_name, response_time_ms=elapsed_ms)
    return text


def _normalize_parser_output(raw: dict[str, Any]) -> dict[str, Any]:
    intents = raw.get("intents")
    if not isinstance(intents, list) or not intents:
        intents = ["chat"]

    allowed = {"schedule", "delete_event", "note", "email", "follow_up", "action_items", "reminder", "checklist", "insights", "chat"}
    parsed_intents = [item for item in intents if isinstance(item, str) and item in allowed]
    if not parsed_intents:
        parsed_intents = ["chat"]

    data = raw.get("data")
    if not isinstance(data, dict):
        data = {}

    return {"intents": parsed_intents, "data": data}


def _build_intent_prompt(message: str, memory_messages: list[str]) -> str:
    memory = "\n".join([f"- {item}" for item in memory_messages]) if memory_messages else "- (no previous context)"
    return (
        f"Schema: {json.dumps(INTENT_JSON_SCHEMA, ensure_ascii=True)}\n"
        "Return exactly one JSON object that follows schema.\n"
        "If multiple actions are present, include all intents in order.\n"
        "Use data fields when possible: title, datetime, duration, note.\n"
        f"Recent messages:\n{memory}\n"
        f"User message: {message}"
    )


def _build_chat_prompt(message: str, memory_messages: list[str]) -> str:
    memory = "\n".join([f"- {item}" for item in memory_messages]) if memory_messages else "- (no previous context)"
    return (
        "You are a concise assistant. Answer in 1 to 2 complete sentences. Do not answer with a single word or fragment.\n"
        f"Recent messages:\n{memory}\n"
        f"User message: {message}"
    )


def _build_schedule_prompt(message: str, start_time: datetime, end_time: datetime, timezone_name: str, duration_minutes: int) -> str:
    return (
        f"Schema: {json.dumps(SCHEDULE_JSON_SCHEMA, ensure_ascii=True)}\n"
        "Return exactly one JSON object that follows schema.\n"
        "Rules:\n"
        "- Use a professional calendar title.\n"
        "- Remove time, date, and filler phrases from the title.\n"
        "- Capitalize names and acronyms properly.\n"
        "- If attendee names are present, keep them as a list of names, not emails.\n"
        "- Use timezone Asia/Kolkata unless the user explicitly specifies a different timezone.\n"
        "- Provide a structured description suitable for Google Calendar.\n"
        f"Resolved start_time: {start_time.isoformat()}\n"
        f"Resolved end_time: {end_time.isoformat()}\n"
        f"Resolved duration_minutes: {duration_minutes}\n"
        f"Resolved timezone: {timezone_name}\n"
        f"User message: {message}"
    )


def _call_gemini_sync(system_prompt: str, user_prompt: str) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY missing")

    if _is_quota_cooldown_active():
        _consume_quota_cooldown_request()
        raise RuntimeError("Gemini quota exceeded - cooldown active")

    # Strict hierarchy: primary model, then configured secondary candidates.
    candidate_models = [GEMINI_MODEL, *GEMINI_MODEL_CANDIDATES]
    seen: set[str] = set()
    ordered_models = [model for model in candidate_models if model and not (model in seen or seen.add(model))]

    last_error: Exception | None = None
    saw_quota_error = False
    for model_name in ordered_models:
        try:
            return _call_gemini_rest_sync(model_name, system_prompt, user_prompt)
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini model failed: %s - %s", model_name, str(exc)[:300])
            if _is_quota_error(exc):
                # record quota events
                incr("gemini_429")
                # Quota exhaustion should return fallback immediately; do not burn calls on other models.
                logger.info("Quota error on model %s; aborting model hierarchy", model_name)
                saw_quota_error = True
                break
            if _is_invalid_model_error(exc):
                logger.info("Invalid model %s; trying next configured candidate", model_name)
                continue
            if _is_non_retryable_gemini_error(exc):
                logger.info("Non-retryable error, skipping model %s", model_name)
                continue

    logger.error("All configured Gemini models exhausted. Last error: %s", str(last_error)[:500])
    if saw_quota_error:
        raise RuntimeError("Gemini quota exceeded") from last_error
    raise RuntimeError("All configured Gemini models failed") from last_error


def _call_gemini_with_timeout_sync(system_prompt: str, user_prompt: str) -> str:
    future = _EXECUTOR.submit(_call_gemini_sync, system_prompt, user_prompt)
    try:
        return future.result(timeout=LLM_TIMEOUT_SECONDS + 0.2)
    except FuturesTimeoutError as exc:
        logger.error("Gemini call timeout")
        raise TimeoutError("Gemini timeout") from exc


async def _call_gemini_with_retry(system_prompt: str, user_prompt: str) -> str:
    # Retryable wrapper with exponential backoff for transient failures.
    last_exc: Exception | None = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                run_in_threadpool(_call_gemini_with_timeout_sync, system_prompt, user_prompt),
                timeout=LLM_TIMEOUT_SECONDS + 0.5,
            )
        except Exception as exc:
            last_exc = exc
            # If quota exhaustion occurred, start cooldown and abort immediately.
            if _is_quota_error(exc):
                logger.warning("Gemini quota error detected on attempt %s", attempt)
                _start_quota_cooldown()
                raise RuntimeError("Gemini quota exceeded") from exc

            # Non-retryable errors should not be retried.
            if _is_non_retryable_gemini_error(exc) and not _is_quota_error(exc):
                logger.warning("Gemini non-retryable error on attempt %s: %s", attempt, str(exc)[:300])
                raise RuntimeError("Gemini failed with non-retryable error") from exc

            # Last attempt: raise and let the caller fallback.
            if attempt == GEMINI_MAX_RETRIES:
                logger.error("Gemini call failed after %s attempts: %s", attempt, str(exc)[:500])
                raise RuntimeError("Gemini failed after retries") from exc

            # Transient error: backoff and retry.
            backoff = GEMINI_BACKOFF_BASE ** (attempt - 1)
            logger.info("Transient Gemini error, retrying in %.1fs (attempt %s/%s): %s", backoff, attempt, GEMINI_MAX_RETRIES, str(exc)[:200])
            await asyncio.sleep(backoff)


async def call_llm_with_timeout(message: str) -> str:
    prompt = _build_chat_prompt(message=message, memory_messages=[])
    return await _call_gemini_with_retry("You are a concise assistant.", prompt)


async def intent_parser(message: str, memory_messages: list[str]) -> dict[str, Any]:
    user_prompt = _build_intent_prompt(message=message, memory_messages=memory_messages)
    try:
        raw = await _call_gemini_with_retry(SYSTEM_PROMPT, user_prompt)
        parsed = _parse_json_with_cleanup_retry(raw)
        logger.info("Intent parser success: intents=%s", parsed.get("intents"))
        return _normalize_parser_output(parsed)
    except Exception as exc:
        logger.warning("Gemini intent parser failed, falling back to local parser: %s", str(exc)[:300])
        # Use local heuristic intent parser when Gemini is unavailable.
        return fallback_intent_parser(message)


def fallback_intent_parser(message: str) -> dict[str, Any]:
    text = message.lower()
    intents: list[str] = []
    has_time_or_date = bool(
        re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", text)
        or re.search(r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
        or re.search(r"\bevery\b", text)
    )
    if any(token in text for token in ["schedule", "meeting", "appointment", "calendar"]) or (
        has_time_or_date and any(token in text for token in ["create", "plan", "sync", "set", "arrange"])
    ):
        intents.append("schedule")
    if any(token in text for token in ["delete", "remove", "cancel"]):
        intents.append("delete_event")
    if any(token in text for token in ["note", "remember", "remind"]):
        intents.append("note")
    if any(token in text for token in ["email", "invite", "draft", "send to attendees"]):
        intents.append("email")
    if any(token in text for token in ["follow up", "follow-up", "recap", "summary"]):
        intents.append("follow_up")
    if any(token in text for token in ["action items", "next steps"]):
        intents.append("action_items")
    if any(token in text for token in ["checklist", "prep", "preparation"]):
        intents.append("checklist")
    if any(token in text for token in ["reminder", "remind me", "notify me"]):
        intents.append("reminder")
    if any(token in text for token in ["insight", "productivity", "burnout", "analytics", "report"]):
        intents.append("insights")
    if not intents:
        intents = ["chat"]
    return {"intents": intents, "data": {}}


def _normalize_schedule_payload(raw: dict[str, Any], message: str, start_time: datetime, end_time: datetime) -> ScheduleMetadata:
    fallback = build_schedule_metadata(
        original_prompt=message,
        parsed_datetime=start_time,
        duration_minutes=max(1, int(round((end_time - start_time).total_seconds() / 60))),
    )

    title = str(raw.get("title") or fallback.title).strip()
    description = str(raw.get("description") or fallback.description).strip()
    timezone_name = str(raw.get("timezone") or fallback.timezone).strip() or fallback.timezone
    event_type = str(raw.get("event_type") or fallback.event_type).strip() or fallback.event_type

    attendees = raw.get("attendees")
    if not isinstance(attendees, list):
        attendees = fallback.attendees
    normalized_attendees = [str(item).strip() for item in attendees if str(item).strip()]

    try:
        duration_minutes = int(float(raw.get("duration_minutes") or fallback.duration_minutes))
    except Exception:
        duration_minutes = fallback.duration_minutes

    try:
        confidence = float(raw.get("confidence") or fallback.confidence)
    except Exception:
        confidence = fallback.confidence

    return ScheduleMetadata(
        original_prompt=fallback.original_prompt,
        title=title[:255] or fallback.title,
        description=description or fallback.description,
        attendees=normalized_attendees or fallback.attendees,
        timezone=timezone_name,
        event_type=event_type,
        confidence=max(0.0, min(round(confidence, 2), 0.99)),
        parsed_datetime=start_time,
        duration_minutes=max(1, duration_minutes),
    )


def local_chat_fallback(message: str) -> str:
    text = message.strip().lower()
    if "machine learning" in text:
        return (
            "Machine learning is when a computer learns patterns from examples instead of being given every rule. "
            "Like learning to recognize spam email by seeing many spam and non-spam examples."
        )
    if any(token in text for token in ["joke", "funny", "humor"]):
        return "Why do programmers prefer dark mode? Because light attracts bugs."
    if "hello" in text or "hi" in text:
        return "Hello! I can help with notes, scheduling, and calendar cleanup tasks."
    if any(token in text for token in ["what can you do", "help", "capabilities"]):
        return "I can help schedule meetings, manage notes, summarize plans, and answer basic questions while Gemini is unavailable."
    return "I am currently in fallback mode, but I can still help with notes and scheduling commands."


def _gemini_failure_message(exc: Exception, message: str) -> str:
    if _is_quota_error(exc):
        return f"{local_chat_fallback(message)} (Gemini quota exceeded; using local fallback.)"
    text = str(exc).lower()
    if "missing" in text and "api_key" in text:
        return f"{local_chat_fallback(message)} (GOOGLE_API_KEY is not configured.)"
    if "invalid_model" in text or _is_invalid_model_error(exc):
        return f"{local_chat_fallback(message)} (Unsupported Gemini model configured.)"
    if "timeout" in text:
        return f"{local_chat_fallback(message)} (Gemini request timed out; using local fallback.)"
    if "network" in text or "connection" in text:
        return f"{local_chat_fallback(message)} (Gemini network error; using local fallback.)"
    return local_chat_fallback(message)


async def _generate_chat_reply(message: str, memory_messages: list[str]) -> str:
    user_prompt = _build_chat_prompt(message=message, memory_messages=memory_messages)
    # One Gemini generation pass per chat request; no duplicate expansion calls.
    return await _call_gemini_with_retry("You are a concise assistant.", user_prompt)


async def generate_schedule_metadata(message: str, start_time: datetime, end_time: datetime, timezone_name: str) -> ScheduleMetadata:
    duration_minutes = max(1, int(round((end_time - start_time).total_seconds() / 60)))
    if not GOOGLE_API_KEY:
        return build_schedule_metadata(
            original_prompt=message,
            parsed_datetime=start_time,
            duration_minutes=duration_minutes,
            timezone=timezone_name,
        )

    user_prompt = _build_schedule_prompt(message, start_time, end_time, timezone_name, duration_minutes)
    try:
        raw = await _call_gemini_with_retry(
            "You produce strict JSON only for professional calendar event extraction.",
            user_prompt,
        )
        parsed = _parse_json_with_cleanup_retry(raw)
        logger.info("TITLE_GENERATED via Gemini: title=%s confidence=%s", parsed.get("title"), parsed.get("confidence"))
        return _normalize_schedule_payload(parsed, message, start_time, end_time)
    except Exception as exc:
        logger.warning("Gemini schedule extraction failed, using local formatter: %s", str(exc)[:300])
        return build_schedule_metadata(
            original_prompt=message,
            parsed_datetime=start_time,
            duration_minutes=duration_minutes,
            timezone=timezone_name,
        )


async def action_executor(
    db: AsyncSession,
    user_id: int,
    message: str,
    parsed_intent: dict[str, Any],
    memory_messages: list[str],
) -> dict[str, Any]:
    from app.services.deletion_service import handle_delete_intent
    from app.services.analytics_service import build_dashboard_analytics
    from app.services.assistant_templates_service import build_template_response
    from app.services.notes_service import create_note
    from app.services.scheduling_service import handle_schedule_intent

    intents: list[str] = parsed_intent.get("intents", ["chat"])
    data: dict[str, Any] = parsed_intent.get("data", {})

    actions: list[dict[str, Any]] = []
    response_parts: list[str] = []

    for intent in intents:
        if intent == "schedule":
            title = str(data.get("title") or "Meeting").strip()
            dt = str(data.get("datetime") or "").strip()
            duration = str(data.get("duration") or "1 hour").strip()

            # Use the original user message when scheduling so the
            # local scheduling parser can extract explicit ranges and
            # duration phrases reliably (e.g. "from 3pm to 5pm", "2-hour").
            schedule_text = message
            result = await handle_schedule_intent(db, user_id, schedule_text)
            actions.append({"type": "schedule", "status": "success" if result.get("success") else "failed", "details": result.get("event")})
            response_parts.append(result.get("response", "Schedule processed."))
            continue

        if intent == "delete_event":
            delete_context = str(data.get("datetime") or message)
            result = await handle_delete_intent(db, user_id, delete_context)
            actions.append({"type": "delete_event", "status": "success", "details": {"deleted": result.get("deleted")}})
            response_parts.append(result.get("response", "Delete processed."))
            continue

        if intent == "note":
            note_text = str(data.get("note") or message).strip()
            if note_text:
                note = await create_note(db, user_id, note_text)
                actions.append({"type": "note", "status": "success", "details": {"note_id": note.id}})
                response_parts.append("Note saved.")
            else:
                actions.append({"type": "note", "status": "failed", "details": {"error": "Empty note"}})
            continue

        if intent in {"email", "follow_up", "action_items", "reminder", "checklist"}:
            template = build_template_response(message)
            actions.append({"type": intent, "status": "success", "details": {"title": template.title, "subject": template.subject}})
            response_parts.append(template.body)
            continue

        if intent == "insights":
            analytics = await build_dashboard_analytics(db, user_id)
            summary = analytics.get("executive_insights", {}).get("weekly_summary") if isinstance(analytics, dict) else None
            if not summary:
                summary = f"You had {analytics.get('total_meetings', 0)} meetings this week."
            actions.append({"type": "insights", "status": "success", "details": {"productivity_score": analytics.get("productivity_score")}})
            response_parts.append(summary)
            continue

        try:
            chat_reply = await _generate_chat_reply(message=message, memory_messages=memory_messages)
            actions.append({"type": "chat", "status": "success"})
            response_parts.append(chat_reply)
        except Exception as exc:
            logger.warning("Fallback chat triggered due to Gemini failure: %s", str(exc)[:300])
            actions.append({"type": "chat", "status": "fallback", "details": {"error": "Gemini unavailable"}})
            response_parts.append(_gemini_failure_message(exc, message))

    intent_label = intents[0] if len(intents) == 1 else "multi"
    safe_response = " ".join(part for part in response_parts if part).strip() or "I could not process your request right now."

    return {
        "intent": intent_label,
        "response": safe_response,
        "actions": actions,
    }


def shutdown_ai_executor() -> None:
    _EXECUTOR.shutdown(wait=False)
