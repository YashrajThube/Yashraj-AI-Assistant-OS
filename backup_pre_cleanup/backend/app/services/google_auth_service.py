import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.core.config import APP_TIMEZONE, GOOGLE_CLIENT_SECRETS_FILE, GOOGLE_REDIRECT_URI, GOOGLE_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/calendar"]
logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    pass


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# OAuth helper stores a single token file for non-authenticated local usage.
def _client_secrets_path() -> Path:
    return Path(GOOGLE_CLIENT_SECRETS_FILE)


def _token_path() -> Path:
    return Path(GOOGLE_TOKEN_FILE)


def _new_flow(state: str | None = None, code_verifier: str | None = None):
    try:
        from google_auth_oauthlib.flow import Flow
    except Exception as exc:
        raise GoogleAuthError("Google auth dependencies are missing. Install requirements first.") from exc

    path = _client_secrets_path()
    if not path.exists():
        raise GoogleAuthError(f"Google OAuth client secrets file not found: {path}")

    try:
        client_data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.exception("Failed to parse Google OAuth client secrets file", extra={"path": str(path)})
        raise GoogleAuthError(f"Google OAuth client secrets file is not valid JSON: {path}") from exc

    if "web" not in client_data:
        logger.error(
            "Google OAuth client secrets file has the wrong OAuth client type",
            extra={"path": str(path), "top_level_keys": list(client_data.keys())},
        )
        raise GoogleAuthError(
            "Google OAuth client secrets file must contain a top-level 'web' object (Web application client)."
        )

    flow = Flow.from_client_secrets_file(str(path), scopes=SCOPES, state=state, code_verifier=code_verifier)
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    logger.info(
        "Initialized OAuth flow",
        extra={
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "client_secrets_path": str(path),
            "state_present": bool(state),
            "code_verifier_present": bool(code_verifier),
        },
    )
    return flow


def _save_credentials(credentials: Any) -> None:
    token_file = _token_path()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    logger.info(
        "Saved Google OAuth credentials",
        extra={
            "token_file": str(token_file),
            "has_refresh_token": bool(getattr(credentials, "refresh_token", None)),
            "expiry": credentials.expiry.isoformat() if getattr(credentials, "expiry", None) else None,
        },
    )


def _load_credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception as exc:
        raise GoogleAuthError("Google auth dependencies are missing. Install requirements first.") from exc

    token_file = _token_path()
    if not token_file.exists():
        logger.info("Google token file not found during credential load", extra={"token_file": str(token_file)})
        raise GoogleAuthError("Google account not connected. Complete OAuth first.")

    logger.info("Loading Google credentials from token file", extra={"token_file": str(token_file)})
    data = json.loads(token_file.read_text(encoding="utf-8"))
    credentials = Credentials.from_authorized_user_info(data, SCOPES)
    logger.info(
        "Loaded Google credentials",
        extra={
            "token_file": str(token_file),
            "expired": bool(credentials.expired),
            "valid": bool(credentials.valid),
            "has_refresh_token": bool(credentials.refresh_token),
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        },
    )

    if credentials.expired and credentials.refresh_token:
        logger.info("Refreshing expired Google credentials", extra={"token_file": str(token_file)})
        credentials.refresh(Request())
        _save_credentials(credentials)

    if not credentials.valid:
        logger.error(
            "Stored Google credentials are invalid after load",
            extra={"token_file": str(token_file), "has_refresh_token": bool(credentials.refresh_token)},
        )
        raise GoogleAuthError("Stored Google credentials are invalid. Reconnect OAuth.")

    return credentials


def _build_authorization_url_sync() -> tuple[str, str, str]:
    flow = _new_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    code_verifier = flow.code_verifier or ""
    logger.info(
        "Generated OAuth authorization URL",
        extra={
            "state_present": bool(state),
            "code_verifier_present": bool(code_verifier),
            "redirect_uri": GOOGLE_REDIRECT_URI,
        },
    )
    return authorization_url, state, code_verifier


async def build_authorization_url() -> tuple[str, str, str]:
    return await run_in_threadpool(_build_authorization_url_sync)


def _exchange_code_for_tokens_sync(code: str, state: str, code_verifier: str | None = None) -> dict:
    flow = _new_flow(state=state, code_verifier=code_verifier)
    token_file = _token_path()
    logger.info(
        "Exchanging OAuth code for tokens",
        extra={
            "state_present": True,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "client_secrets_path": str(_client_secrets_path()),
            "token_file": str(token_file),
            "code_length": len(code),
            "code_verifier_present": bool(code_verifier),
        },
    )
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.exception(
            "Google OAuth token exchange failed",
            extra={
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "state_present": True,
                "client_secrets_path": str(_client_secrets_path()),
                "token_file": str(token_file),
                "code_length": len(code),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            },
        )
        raise GoogleAuthError(f"OAuth token exchange failed: {type(exc).__name__}: {exc}") from exc

    credentials = flow.credentials
    logger.info(
        "Google OAuth token exchange completed",
        extra={
            "has_refresh_token": bool(getattr(credentials, "refresh_token", None)),
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            "token_uri": getattr(credentials, "token_uri", None),
        },
    )
    _save_credentials(credentials)
    return {
        "success": True,
        "email": getattr(credentials, "account", None),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }


async def exchange_code_for_tokens(code: str, state: str, code_verifier: str | None = None) -> dict:
    return await run_in_threadpool(_exchange_code_for_tokens_sync, code, state, code_verifier)


async def load_saved_credentials():
    try:
        return await run_in_threadpool(_load_credentials)
    except GoogleAuthError:
        logger.info("No usable Google credentials are currently stored")
        return None


async def get_auth_status() -> dict:
    try:
        logger.info("Checking Google auth status")
        creds = await run_in_threadpool(_load_credentials)
        logger.info(
            "Google auth status check completed",
            extra={"connected": True, "expiry": creds.expiry.isoformat() if creds.expiry else None},
        )
        return {
            "connected": True,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }
    except GoogleAuthError:
        logger.info("Google auth status check completed", extra={"connected": False})
        return {"connected": False, "expiry": None}


def _create_google_calendar_event_sync(
    credentials,
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None = None,
    color_id: str | None = None,
    attendees: list[str] | None = None,
    create_meet_link: bool = True,
    reminders: list[int] | None = None,
) -> dict:
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise GoogleAuthError("Google Calendar API dependency is missing. Install requirements first.") from exc

    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    event_body = build_google_event_payload(
        title,
        start_time,
        end_time,
        description=description,
        color_id=color_id,
        attendees=attendees,
        create_meet_link=create_meet_link,
        reminders=reminders,
    )

    result = service.events().insert(calendarId="primary", body=event_body, conferenceDataVersion=1).execute()
    return {
        "id": result.get("id"),
        "htmlLink": result.get("htmlLink"),
    }


async def create_google_calendar_event(
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None = None,
    color_id: str | None = None,
    attendees: list[str] | None = None,
    create_meet_link: bool = True,
    reminders: list[int] | None = None,
) -> dict:
    logger.info(
        "Starting Google Calendar event creation",
        extra={
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "has_description": bool(description),
            "attendee_count": len(attendees or []),
            "create_meet_link": create_meet_link,
            "has_reminders": bool(reminders),
        },
    )
    try:
        credentials = await run_in_threadpool(_load_credentials)
        result = await run_in_threadpool(
            _create_google_calendar_event_sync,
            credentials,
            title,
            start_time,
            end_time,
            description,
            color_id,
            attendees,
            create_meet_link,
            reminders,
        )
        logger.info(
            "Google Calendar event creation completed",
            extra={"title": title, "google_event_id": result.get("id"), "has_html_link": bool(result.get("htmlLink"))},
        )
        return result
    except Exception:
        logger.exception(
            "Google Calendar event creation failed",
            extra={
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendee_count": len(attendees or []),
            },
        )
        raise


def build_google_event_payload(
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None = None,
    color_id: str | None = None,
    attendees: list[str] | None = None,
    create_meet_link: bool = True,
    reminders: list[int] | None = None,
) -> dict:
    valid_attendees = [item for item in (attendees or []) if item and _EMAIL_RE.match(item)]
    skipped_attendees = [item for item in (attendees or []) if item and item not in valid_attendees]
    if skipped_attendees:
        logger.info(
            "Skipping non-email attendees for Google Calendar payload",
            extra={"skipped_attendees": skipped_attendees, "title": title},
        )

    payload = {
        "summary": title,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": APP_TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": APP_TIMEZONE,
        },
    }
    if description:
        payload["description"] = description
    if color_id:
        payload["colorId"] = color_id
    if valid_attendees:
        payload["attendees"] = [{"email": item} for item in valid_attendees]
    if reminders:
        payload["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": max(1, int(item))} for item in reminders],
        }
    if create_meet_link:
        payload["conferenceData"] = {
            "createRequest": {
                "requestId": f"ai-assistant-{int(start_time.timestamp())}-{abs(hash(title)) % 100000}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    return payload


def _delete_google_calendar_event_sync(credentials, event_id: str) -> None:
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise GoogleAuthError("Google Calendar API dependency is missing. Install requirements first.") from exc

    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    service.events().delete(calendarId="primary", eventId=event_id).execute()


async def delete_google_calendar_event(event_id: str) -> None:
    credentials = await run_in_threadpool(_load_credentials)
    await run_in_threadpool(_delete_google_calendar_event_sync, credentials, event_id)
