"""
Notifications endpoint — allows users to query their own notifications.
Used by E2E tests to verify notification insertion.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.models.notification import Notification
from app.deps.auth import get_current_user, require_admin
from app.models.user import User


class NotificationResponse(BaseModel):
    id: uuid.UUID
    recipient_id: uuid.UUID
    triggered_by: uuid.UUID
    entry_id: Optional[uuid.UUID] = None
    action: str
    message: str
    created_at: datetime
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationResponse])
async def list_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notifications for the current user."""
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


@router.get("/all", response_model=List[NotificationResponse])
async def list_all_notifications(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Admin-only: list ALL notifications (for E2E / debugging)."""
    result = await db.execute(
        select(Notification).order_by(Notification.created_at.desc())
    )
    return result.scalars().all()
