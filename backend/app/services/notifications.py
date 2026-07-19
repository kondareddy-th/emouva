"""
Notification service — creates in-app notifications for users.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    rule_id: uuid.UUID | None = None,
) -> Notification:
    """Create and persist a notification for a user."""
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        rule_id=rule_id,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    logger.info("Notification created for user %s: %s", user_id, title)
    return notif
