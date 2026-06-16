from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import requests

from app.core.config import DATABASE_URL, ENABLE_JWT_AUTH, GEMINI_MODEL, GOOGLE_API_KEY, LLM_TIMEOUT_SECONDS, SECRET_KEY, JWT_SECRET_KEY


@dataclass(slots=True)
class ValidationCheck:
    name: str
    status: str
    message: str


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("your_") or "placeholder" in lowered or lowered in {"changeme", "change_me", "replace_me"}


def validate_environment() -> dict[str, Any]:
    checks: list[ValidationCheck] = []

    if DATABASE_URL.strip():
        checks.append(ValidationCheck("database_url", "ok", "DATABASE_URL configured"))
    else:
        checks.append(ValidationCheck("database_url", "missing", "DATABASE_URL is not configured"))

    if GOOGLE_API_KEY.strip() and not _is_placeholder(GOOGLE_API_KEY):
        checks.append(ValidationCheck("google_api_key", "ok", "GOOGLE_API_KEY configured"))
    else:
        checks.append(ValidationCheck("google_api_key", "missing", "GOOGLE_API_KEY is not configured"))

    if GEMINI_MODEL.strip():
        checks.append(ValidationCheck("gemini_model", "ok", f"GEMINI_MODEL={GEMINI_MODEL}"))
    else:
        checks.append(ValidationCheck("gemini_model", "missing", "GEMINI_MODEL is not configured"))

    secret_value = SECRET_KEY or JWT_SECRET_KEY
    if secret_value.strip():
        checks.append(ValidationCheck("secret_key", "ok", "SECRET_KEY configured"))
    elif ENABLE_JWT_AUTH:
        checks.append(ValidationCheck("secret_key", "missing", "SECRET_KEY / JWT_SECRET_KEY is not configured"))
    else:
        checks.append(ValidationCheck("secret_key", "optional", "SECRET_KEY is optional because JWT auth is disabled"))

    issues = [check.message for check in checks if check.status == "missing"]
    return {
        "ok": not issues,
        "issues": issues,
        "checks": [asdict(check) for check in checks],
    }


def probe_gemini_configuration() -> dict[str, Any]:
    if not GOOGLE_API_KEY.strip() or _is_placeholder(GOOGLE_API_KEY):
        return {
            "status": "missing",
            "message": "GOOGLE_API_KEY is not configured",
            "model": GEMINI_MODEL,
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}?key={GOOGLE_API_KEY}"
    try:
        response = requests.get(url, timeout=LLM_TIMEOUT_SECONDS)
    except requests.Timeout:
        return {
            "status": "timeout",
            "message": "Gemini health check timed out",
            "model": GEMINI_MODEL,
        }
    except requests.RequestException as exc:
        return {
            "status": "network_error",
            "message": f"Gemini network error: {exc}",
            "model": GEMINI_MODEL,
        }

    if response.status_code == 200:
        return {
            "status": "ok",
            "message": "Gemini API is reachable",
            "model": GEMINI_MODEL,
        }

    text = response.text[:300]
    if response.status_code in {401, 403}:
        status = "invalid_key"
        message = "Invalid Gemini API key"
    elif response.status_code == 404:
        status = "invalid_model"
        message = f"Unsupported Gemini model: {GEMINI_MODEL}"
    elif response.status_code == 429:
        status = "quota_exceeded"
        message = "Gemini quota exceeded"
    else:
        status = "error"
        message = f"Gemini API error ({response.status_code}): {text}"

    return {
        "status": status,
        "message": message,
        "model": GEMINI_MODEL,
        "http_status": response.status_code,
    }
