import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import error_response, ok_response
from app.db.database import get_db
from app.services.analytics_service import build_dashboard_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
DEFAULT_USER_ID = 1
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def dashboard_analytics(db: AsyncSession = Depends(get_db)):
    try:
        analytics = await build_dashboard_analytics(db, DEFAULT_USER_ID)
    except Exception:
        logger.exception("API error while building dashboard analytics")
        return error_response(message="Failed to load analytics", status_code=503)

    return ok_response(data={"analytics": analytics}, message="Dashboard analytics fetched")
