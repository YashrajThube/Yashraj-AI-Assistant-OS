import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.core.responses import error_response, ok_response
from app.services.google_auth_service import (
    GoogleAuthError,
    build_authorization_url,
    exchange_code_for_tokens,
    get_auth_status,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_CODE_VERIFIER_COOKIE = "oauth_code_verifier"


@router.get("/login")
async def google_login():
    try:
        authorization_url, state, code_verifier = await build_authorization_url()
        response = RedirectResponse(url=authorization_url, status_code=302)
        response.set_cookie(
            key=OAUTH_STATE_COOKIE,
            value=state,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
            max_age=300,
        )
        response.set_cookie(
            key=OAUTH_CODE_VERIFIER_COOKIE,
            value=code_verifier,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
            max_age=300,
        )
        return response
    except GoogleAuthError as exc:
        return error_response(message=str(exc), status_code=400)
    except Exception:
        logger.exception("API error while starting Google OAuth")
        return error_response(message="Failed to start Google OAuth", status_code=503)


@router.get("/callback")
async def google_callback(request: Request, code: str = Query(...), state: str = Query(...)):
    try:
        cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
        code_verifier = request.cookies.get(OAUTH_CODE_VERIFIER_COOKIE)
        logger.info(
            "Google OAuth callback received",
            extra={
                "has_code": bool(code),
                "code_length": len(code),
                "has_state": bool(state),
                "cookie_state_present": bool(cookie_state),
                "code_verifier_present": bool(code_verifier),
                "cookie_matches_query_state": bool(cookie_state and cookie_state == state),
                "redirect_path": str(request.url),
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        if not cookie_state or cookie_state != state:
            logger.error(
                "Google OAuth callback state mismatch",
                extra={"cookie_state_present": bool(cookie_state), "has_code": bool(code), "has_state": bool(state)},
            )
            return error_response(message="Invalid OAuth state", status_code=400)
        if not code_verifier:
            logger.error(
                "Missing PKCE code verifier cookie during OAuth callback",
                extra={"has_code": bool(code), "has_state": bool(state)},
            )
            return error_response(message="Missing OAuth code verifier", status_code=400)

        result = await exchange_code_for_tokens(code=code, state=state, code_verifier=code_verifier)
        response = ok_response(data={"auth": result}, message="Google Calendar connected successfully")
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        response.delete_cookie(OAUTH_CODE_VERIFIER_COOKIE, path="/")
        return response
    except GoogleAuthError as exc:
        logger.exception(
            "Google OAuth callback failed with a GoogleAuthError",
            extra={"has_code": bool(code), "has_state": bool(state)},
        )
        response = error_response(message=str(exc), status_code=400)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        response.delete_cookie(OAUTH_CODE_VERIFIER_COOKIE, path="/")
        return response
    except Exception:
        logger.exception(
            "API error while processing Google OAuth callback",
            extra={"has_code": bool(code), "has_state": bool(state)},
        )
        response = error_response(message="Google OAuth callback failed", status_code=503)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        response.delete_cookie(OAUTH_CODE_VERIFIER_COOKIE, path="/")
        return response


@router.get("/status")
async def auth_status():
    try:
        status = await get_auth_status()
    except Exception:
        logger.exception("API error while checking Google auth status")
        return error_response(message="Failed to fetch auth status", status_code=503)

    return ok_response(data={"auth": status}, message="Google auth status fetched")
