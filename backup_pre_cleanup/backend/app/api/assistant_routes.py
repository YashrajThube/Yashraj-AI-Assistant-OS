import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import error_response, ok_response
from app.db.database import get_db
from app.schemas.assistant_schema import ChatRequest
from app.services.assistant_service import process_ai_background_job, process_chat_message

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
DEFAULT_USER_ID = 1
logger = logging.getLogger(__name__)


async def _handle_chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await process_chat_message(db, DEFAULT_USER_ID, request.message)
    except Exception:
        logger.exception("API error while processing assistant chat")
        return error_response(
            message="Assistant request failed",
            status_code=503,
            data={
                "intent": "chat",
                "response": "The assistant is temporarily unavailable.",
                "actions": [{"type": "chat", "status": "failed"}],
            },
        )

    message = str(result.get("response", "Request processed"))
    data = {
        "intent": result.get("intent", "chat"),
        "response": message,
        "actions": result.get("actions", []),
    }
    return ok_response(data=data, message=message)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    background_ai: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if background_ai:
        background_tasks.add_task(process_ai_background_job, DEFAULT_USER_ID, request.message)
        return ok_response(
            data={"intent": "chat", "response": "AI processing started in background"},
            message="Accepted",
            status_code=202,
        )

    return await _handle_chat(request=request, background_tasks=background_tasks, db=db)


@router.post("/voice")
async def voice(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    background_ai: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if background_ai:
        background_tasks.add_task(process_ai_background_job, DEFAULT_USER_ID, request.message)
        return ok_response(
            data={"intent": "chat", "response": "AI processing started in background"},
            message="Accepted",
            status_code=202,
        )

    return await _handle_chat(request=request, background_tasks=background_tasks, db=db)
