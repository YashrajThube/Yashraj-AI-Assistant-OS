import asyncio
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import SessionLocal
from app.models.failed_job_model import FailedJob

logger = logging.getLogger(__name__)
RETRY_DELAYS_SECONDS = [60, 300, 900]
MAX_RETRIES = 3


async def create_failed_job(db: AsyncSession, job_type: str, payload: dict[str, Any], status: str = "pending") -> FailedJob:
    job = FailedJob(
        type=job_type,
        payload=json.dumps(payload, ensure_ascii=True),
        retry_count=0,
        status=status,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def run_retry_job(job_id: int) -> None:
    # Background retry loop with exponential backoff (1m, 5m, 15m).
    while True:
        async with SessionLocal() as db:
            job = (await db.execute(select(FailedJob).where(FailedJob.id == job_id))).scalar_one_or_none()
            if job is None:
                return

            if job.status == "completed" or job.retry_count >= MAX_RETRIES:
                return

            payload = json.loads(job.payload)
            try:
                if job.type == "google_sync":
                    from app.services.calendar_service import sync_google_event_for_retry

                    await sync_google_event_for_retry(db, int(payload["event_id"]))
                elif job.type == "ai_chat":
                    from app.services.assistant_service import process_ai_background_job

                    await process_ai_background_job(int(payload.get("user_id", 1)), str(payload.get("message", "")))
                else:
                    raise ValueError(f"Unsupported retry job type: {job.type}")

                job.status = "completed"
                await db.commit()
                return
            except Exception as exc:
                job.retry_count += 1
                if job.retry_count >= MAX_RETRIES:
                    job.status = "failed"
                    await db.commit()
                    logger.error("Retry job permanently failed job_id=%s type=%s error=%s", job.id, job.type, exc, exc_info=True)
                    return

                job.status = "retrying"
                await db.commit()
                delay = RETRY_DELAYS_SECONDS[min(job.retry_count - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                logger.warning(
                    "Retry job failed job_id=%s type=%s retry_count=%s next_delay_seconds=%s error=%s",
                    job.id,
                    job.type,
                    job.retry_count,
                    delay,
                    exc,
                )

        await asyncio.sleep(delay)
