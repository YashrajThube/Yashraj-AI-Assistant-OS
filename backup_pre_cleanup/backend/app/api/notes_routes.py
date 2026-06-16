import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import error_response, ok_response
from app.db.database import get_db
from app.schemas.note_schema import NoteCreate, NoteOut
from app.services.notes_service import create_note, get_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])
DEFAULT_USER_ID = 1
logger = logging.getLogger(__name__)


@router.post("")
async def create_note_entry(
    payload: NoteCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        note = await create_note(db, DEFAULT_USER_ID, payload.content)
    except Exception:
        logger.exception("API error while creating note")
        return error_response(message="Failed to create note", status_code=503)

    return ok_response(
        data={"note": NoteOut.model_validate(note).model_dump(mode="json")},
        message="Note created",
    )


@router.get("")
async def list_note_entries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        notes = [
            NoteOut.model_validate(item).model_dump(mode="json")
            for item in await get_notes(db, DEFAULT_USER_ID, limit=limit, offset=offset)
        ]
    except Exception:
        logger.exception("API error while listing notes")
        return error_response(message="Failed to fetch notes", status_code=503)

    return ok_response(data={"notes": notes}, message="Notes fetched")
