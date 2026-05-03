from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Notification
from app.schemas.schemas import NotificationResponse

router = APIRouter()


@router.get("/")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.sent_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()
    unread = sum(1 for n in notifications if not n.is_read)
    return {
        "notifications": [NotificationResponse.model_validate(n) for n in notifications],
        "unread_count": unread,
    }


@router.post("/mark-read/{notification_id}")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    return {"status": "ok"}


@router.post("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    return {"status": "ok"}
