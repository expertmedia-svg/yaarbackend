from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, UserRole, Surveyor, Survey, SurveyPhoto, Commerce, Category
from app.schemas.schemas import (
    SurveyCreate, SurveyResponse, SurveyorResponse, SurveyorCreate,
    PaginationResponse
)

router = APIRouter(prefix="/surveyors", tags=["Surveyor"])


# ── Surveyor Management ────────────────────────────────────────────────────────

@router.post("/register", response_model=SurveyorResponse)
async def register_surveyor(
    data: SurveyorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register as a surveyor (field agent)"""
    if current_user.role not in [UserRole.SURVEYOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    if existing.scalar():
        raise HTTPException(status_code=400, detail="Already registered as surveyor")

    surveyor_code = f"SRV{uuid.uuid4().hex[:8].upper()}"
    surveyor = Surveyor(
        user_id=current_user.id,
        surveyor_code=surveyor_code,
        region=data.region,
        city=data.city,
        quartier=data.quartier,
        is_active=True,
        total_stores_surveyed=0,
        verification_score=0.0
    )
    db.add(surveyor)
    await db.commit()
    await db.refresh(surveyor)
    return surveyor


@router.get("/profile", response_model=SurveyorResponse)
async def get_surveyor_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current surveyor profile"""
    surveyor = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = surveyor.scalar_one_or_none()
    if not surveyor:
        raise HTTPException(status_code=404, detail="Surveyor profile not found")
    return surveyor


@router.get("/stats")
async def get_surveyor_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get surveyor statistics"""
    surveyor = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = surveyor.scalar_one_or_none()
    if not surveyor:
        raise HTTPException(status_code=404, detail="Surveyor profile not found")

    result = await db.execute(
        select(Survey).where(Survey.surveyor_id == surveyor.id)
    )
    surveys = result.scalars().all()

    verified = sum(1 for s in surveys if s.status == "verified")
    pending = sum(1 for s in surveys if s.status == "pending")
    rejected = sum(1 for s in surveys if s.status == "rejected")

    return {
        "total_surveys": len(surveys),
        "verified": verified,
        "pending": pending,
        "rejected": rejected,
        "verification_score": surveyor.verification_score,
        "last_sync": surveyor.last_sync,
        "sync_status": surveyor.sync_status
    }


# ── Survey Creation & Management ───────────────────────────────────────────────

@router.post("/surveys", response_model=SurveyResponse)
async def create_survey(
    data: SurveyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new store survey"""
    surveyor = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = surveyor.scalar_one_or_none()
    if not surveyor:
        raise HTTPException(status_code=404, detail="Surveyor profile not found")

    category = await db.execute(
        select(Category).where(Category.id == data.category_id)
    )
    if not category.scalar():
        raise HTTPException(status_code=404, detail="Category not found")

    survey = Survey(
        surveyor_id=surveyor.id,
        store_name=data.store_name,
        owner_name=data.owner_name,
        category_id=data.category_id,
        subcategory_id=data.subcategory_id,
        phone=data.phone,
        address=data.address,
        city=data.city,
        quartier=data.quartier,
        latitude=data.latitude,
        longitude=data.longitude,
        gps_accuracy=data.gps_accuracy,
        description=data.description,
        opening_hours=data.opening_hours.model_dump() if data.opening_hours else None,
        availability=data.availability,
        services=data.services or [],
        tags=data.tags or [],
        status="pending",
        is_active=True,
        survey_date=datetime.utcnow()
    )
    db.add(survey)
    await db.flush()

    # Add photos
    for photo_data in data.photos:
        photo = SurveyPhoto(
            survey_id=survey.id,
            photo_url=photo_data.photo_url,
            photo_type=photo_data.photo_type
        )
        db.add(photo)

    await db.commit()
    await db.refresh(survey)
    return survey


@router.get("/surveys", response_model=PaginationResponse)
async def list_surveys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """List surveyor's surveys"""
    surveyor = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = surveyor.scalar_one_or_none()
    if not surveyor:
        raise HTTPException(status_code=404, detail="Surveyor profile not found")

    query = select(Survey).where(Survey.surveyor_id == surveyor.id)
    if status:
        query = query.where(Survey.status == status)

    result = await db.execute(query)
    total = len(result.scalars().all())

    result = await db.execute(
        query.order_by(desc(Survey.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/surveys/{survey_id}", response_model=SurveyResponse)
async def get_survey(
    survey_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get survey details"""
    result = await db.execute(
        select(Survey).where(Survey.id == survey_id)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey


@router.post("/surveys/{survey_id}/sync")
async def sync_survey(
    survey_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sync offline survey to server"""
    result = await db.execute(
        select(Survey).where(Survey.id == survey_id)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    survey.synced_at = datetime.utcnow()
    survey.status = "pending"
    await db.commit()

    return {"status": "synced", "survey_id": survey_id}


@router.delete("/surveys/{survey_id}")
async def delete_survey(
    survey_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a survey"""
    result = await db.execute(
        select(Survey).where(Survey.id == survey_id)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    await db.delete(survey)
    await db.commit()
    return {"status": "deleted"}


# ── Offline Sync ───────────────────────────────────────────────────────────────

@router.post("/batch-sync")
async def batch_sync_surveys(
    surveys_data: List[SurveyCreate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Batch sync multiple offline surveys"""
    surveyor = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = surveyor.scalar_one_or_none()
    if not surveyor:
        raise HTTPException(status_code=404, detail="Surveyor profile not found")

    synced_count = 0
    for survey_data in surveys_data:
        survey = Survey(
            surveyor_id=surveyor.id,
            store_name=survey_data.store_name,
            owner_name=survey_data.owner_name,
            category_id=survey_data.category_id,
            phone=survey_data.phone,
            address=survey_data.address,
            city=survey_data.city,
            quartier=survey_data.quartier,
            latitude=survey_data.latitude,
            longitude=survey_data.longitude,
            gps_accuracy=survey_data.gps_accuracy,
            description=survey_data.description,
            opening_hours=survey_data.opening_hours.model_dump() if survey_data.opening_hours else None,
            services=survey_data.services or [],
            tags=survey_data.tags or [],
            status="pending",
            survey_date=datetime.utcnow()
        )
        db.add(survey)
        synced_count += 1

    surveyor.last_sync = datetime.utcnow()
    surveyor.sync_status = "synced"
    await db.commit()

    return {
        "status": "synced",
        "synced_count": synced_count,
        "last_sync": surveyor.last_sync
    }
