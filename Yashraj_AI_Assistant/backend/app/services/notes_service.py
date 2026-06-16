from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note_model import Note


async def create_note(db: AsyncSession, user_id: int, content: str) -> Note:
    note = Note(user_id=user_id, content=content.strip())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def get_notes(db: AsyncSession, user_id: int, limit: int = 50, offset: int = 0) -> list[Note]:
    statement = (
        select(Note)
        .where(Note.user_id == user_id)
        .order_by(Note.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(statement)).all())


async def get_recent_note_messages(db: AsyncSession, user_id: int, limit: int = 5) -> list[str]:
    statement = (
        select(Note)
        .where(Note.user_id == user_id)
        .order_by(Note.created_at.desc())
        .limit(limit)
    )
    notes = list((await db.scalars(statement)).all())
    # Return oldest -> newest ordering for prompt context readability.
    notes.reverse()
    return [item.content for item in notes]
