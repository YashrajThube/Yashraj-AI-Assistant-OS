import logging
import time
from contextlib import asynccontextmanager
import json

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.assistant_routes import router as assistant_router
from app.api.auth_routes import router as auth_router
from app.api.analytics_routes import router as analytics_router
from app.api.calendar_routes import router as calendar_router
from app.api.notes_routes import router as notes_router
from app.core.config import CELERY_BROKER_URL, CORS_ORIGINS, DEBUG, ENABLE_JWT_AUTH, ENABLE_AUDIT_LOGS, GOOGLE_API_KEY, JWT_SECRET_KEY, RATE_LIMIT_PER_MINUTE, REDIS_URL, STARTUP_VALIDATE_GOOGLE_AUTH
from app.core.logging_config import setup_logging
from app.core.responses import error_response, ok_response
from app.db.database import Base, engine, get_db
from app.services.ai_service import shutdown_ai_executor
from app.services.google_auth_service import get_auth_status
from app.monitoring.metrics import get_metrics, render_prometheus
from app.models.failed_job_model import FailedJob
from fastapi.responses import PlainTextResponse
from app.api.admin_routes import router as admin_router

setup_logging()
logger = logging.getLogger(__name__)
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


async def _run_startup_validation() -> None:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(json.dumps({"event": "startup_check", "service": "db", "status": "ok"}, ensure_ascii=True))
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "startup_check",
                    "service": "db",
                    "status": "failed",
                    "error": str(exc)[:500],
                },
                ensure_ascii=True,
            )
        )
        raise RuntimeError("Startup validation failed: database connection error") from exc

    if GOOGLE_API_KEY:
        logger.info(json.dumps({"event": "startup_check", "service": "gemini_key", "status": "ok"}, ensure_ascii=True))
    else:
        logger.warning(
            json.dumps(
                {
                    "event": "startup_check",
                    "service": "gemini_key",
                    "status": "missing",
                    "mode": "fallback_only",
                },
                ensure_ascii=True,
            )
        )

    if STARTUP_VALIDATE_GOOGLE_AUTH:
        try:
            auth = await get_auth_status()
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "startup_check",
                        "service": "google_oauth",
                        "status": "failed",
                        "error": str(exc)[:500],
                    },
                    ensure_ascii=True,
                )
            )
            raise RuntimeError("Startup validation failed: Google OAuth check failed") from exc

        if not auth.get("connected"):
            logger.error(
                json.dumps(
                    {
                        "event": "startup_check",
                        "service": "google_oauth",
                        "status": "failed",
                        "reason": "not_connected",
                    },
                    ensure_ascii=True,
                )
            )
            raise RuntimeError("Startup validation failed: Google OAuth is not connected")

        logger.info(json.dumps({"event": "startup_check", "service": "google_oauth", "status": "ok"}, ensure_ascii=True))

    if ENABLE_JWT_AUTH and not JWT_SECRET_KEY:
        logger.warning(
            json.dumps(
                {
                    "event": "startup_check",
                    "service": "jwt_auth",
                    "status": "missing_secret",
                },
                ensure_ascii=True,
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import models before create_all so SQLAlchemy metadata includes all tables.
    from app.models import event_model, failed_job_model, note_model  # noqa: F401

    await _run_startup_validation()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    shutdown_ai_executor()


app = FastAPI(title="Yashraj AI Assistant API", version="1.0.0", lifespan=lifespan, debug=DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("%s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.middleware("http")
async def rate_limit_requests(request: Request, call_next):
    # Lightweight in-memory limiter for local deployment without external dependencies.
    actor = request.headers.get("X-User-Id") or (request.client.host if request.client else "unknown")
    now = time.time()
    window_start = now - 60

    timestamps = _RATE_LIMIT_BUCKETS.setdefault(actor, [])
    timestamps[:] = [ts for ts in timestamps if ts >= window_start]

    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        return error_response(message="Rate limit exceeded", status_code=429)

    timestamps.append(now)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation failed on %s: %s", request.url.path, exc.errors())
    return error_response(message="Validation error", status_code=422)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTP exception on %s: %s", request.url.path, exc.detail)
    return error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return error_response(
        message="Service temporarily unavailable.",
        status_code=503,
    )


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "connected"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return ok_response(
        data={
            "status": "ok",
            "services": {
                "llm": "available" if GOOGLE_API_KEY else "unavailable",
                "calendar": "available",
                "db": db_status,
                "google_calendar_auth": "per-user",
                "audit_logs": "enabled" if ENABLE_AUDIT_LOGS else "disabled",
            },
        },
        message="Health check completed",
    )


@app.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    queue_depth = 0
    try:
        await db.execute(text("SELECT 1"))
        queue_depth = int((await db.execute(select(func.count()).select_from(FailedJob))).scalar_one())
    except Exception:
        db_status = "disconnected"

    warnings = []
    if ENABLE_JWT_AUTH and not JWT_SECRET_KEY:
        warnings.append("jwt_secret_missing")
    if not REDIS_URL or not CELERY_BROKER_URL:
        warnings.append("queue_backend_missing")

    ready = db_status == "connected" and not warnings
    return ok_response(
        data={
            "ready": ready,
            "environment": "production" if not DEBUG else "development",
            "database": db_status,
            "queue_depth": queue_depth,
            "warnings": warnings,
            "services": {
                "llm": "available" if GOOGLE_API_KEY else "unavailable",
                "google_calendar_auth": "per-user",
            },
        },
        message="Readiness check completed",
    )


app.include_router(assistant_router)
app.include_router(analytics_router)
app.include_router(calendar_router)
app.include_router(notes_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/internal/metrics")
async def internal_metrics(format: str | None = None):
    # By default expose Prometheus text format for easy scraping.
    if format == "json":
        return ok_response(data={"metrics": get_metrics()})
    body = render_prometheus()
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")
