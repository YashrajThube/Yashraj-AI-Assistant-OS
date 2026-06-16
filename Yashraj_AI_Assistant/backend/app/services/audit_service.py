from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.config import ENABLE_AUDIT_LOGS

logger = logging.getLogger(__name__)


def audit_event(event: str, actor: str | int, action: str, details: dict | None = None) -> None:
    if not ENABLE_AUDIT_LOGS:
        return

    payload = {
        "event": event,
        "actor": str(actor),
        "action": action,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(payload, ensure_ascii=True))
