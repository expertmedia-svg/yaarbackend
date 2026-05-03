from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Event
from app.schemas.schemas import EventCreate, EventResponse

router = APIRouter()


@router.get("/")
async def list_events(
    city: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    query = select(Event).where(Event.is_active == True, Event.starts_at >= now)
    if city:
        query = query.where(Event.city == city)
    query = query.order_by(Event.starts_at).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()
    return [EventResponse.model_validate(e) for e in events]


@router.post("/", status_code=201)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    event = Event(**data.model_dump(), created_by=current_user.id)
    db.add(event)
    await db.flush()
    return {"id": event.id, "message": "Événement créé"}
