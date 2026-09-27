from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import re
import unicodedata

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User, UserRole, Surveyor, Survey, SurveyPhoto, Commerce, Category,
    Merchant, CommerceStatus, Product
)
from app.schemas.schemas import (
    SurveyCreate, SurveyResponse, SurveyorResponse, SurveyorCreate,
    PaginationResponse
)

router = APIRouter(prefix="/surveyors", tags=["Surveyor"])


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)


async def _get_or_create_surveyor(db: AsyncSession, user: User) -> Surveyor:
    result = await db.execute(select(Surveyor).where(Surveyor.user_id == user.id))
    surveyor = result.scalar_one_or_none()
    if not surveyor:
        surveyor_code = f"AGT-001" if user.id == "default" else f"AGT-{user.phone[-4:] if len(user.phone) >= 4 else uuid.uuid4().hex[:4].upper()}"
        # Ensure code uniqueness
        existing_code = await db.execute(select(Surveyor).where(Surveyor.surveyor_code == surveyor_code))
        if existing_code.scalar_one_or_none():
            surveyor_code = f"AGT-{uuid.uuid4().hex[:4].upper()}"

        surveyor = Surveyor(
            user_id=user.id,
            surveyor_code=surveyor_code,
            region="Centre",
            city="Ouagadougou",
            quartier="Secteur 12",
            is_active=True,
            total_stores_surveyed=0,
            verification_score=4.9,
            sync_status="synced"
        )
        db.add(surveyor)
        await db.commit()
        await db.refresh(surveyor)
    return surveyor


@router.post("/register", response_model=SurveyorResponse)
async def register_surveyor(
    data: SurveyorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register as a surveyor (field agent)"""
    existing = await db.execute(
        select(Surveyor).where(Surveyor.user_id == current_user.id)
    )
    surveyor = existing.scalar_one_or_none()
    if surveyor:
        return surveyor

    surveyor_code = f"AGT-{uuid.uuid4().hex[:4].upper()}"
    surveyor = Surveyor(
        user_id=current_user.id,
        surveyor_code=surveyor_code,
        region=data.region or "Centre",
        city=data.city or "Ouagadougou",
        quartier=data.quartier or "Secteur 12",
        is_active=True,
        total_stores_surveyed=0,
        verification_score=4.9,
        sync_status="synced"
    )
    db.add(surveyor)
    await db.commit()
    await db.refresh(surveyor)
    return surveyor


@router.get("/profile")
async def get_surveyor_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current surveyor profile with user details"""
    surveyor = await _get_or_create_surveyor(db, current_user)
    return {
        "id": surveyor.id,
        "user_id": surveyor.user_id,
        "surveyor_code": surveyor.surveyor_code,
        "full_name": current_user.full_name or "Agent terrain",
        "phone": current_user.phone,
        "avatar_url": current_user.avatar_url,
        "region": surveyor.region,
        "city": surveyor.city,
        "quartier": surveyor.quartier,
        "is_active": surveyor.is_active,
        "total_stores_surveyed": surveyor.total_stores_surveyed,
        "verification_score": surveyor.verification_score,
        "sync_status": surveyor.sync_status,
        "last_sync": surveyor.last_sync
    }


@router.get("/stats")
async def get_surveyor_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get surveyor statistics matching Screen 1 (Commerces, Produits, En attente)"""
    surveyor = await _get_or_create_surveyor(db, current_user)

    # Count surveys/commerces
    surveys_res = await db.execute(select(Survey).where(Survey.surveyor_id == surveyor.id))
    surveys = surveys_res.scalars().all()
    commerces_count = sum(1 for s in surveys if s.status in ["verified", "active"])
    pending_commerces = sum(1 for s in surveys if s.status == "pending")

    # Count products
    prod_res = await db.execute(select(Product).where(Product.created_by == current_user.id))
    products = prod_res.scalars().all()
    products_count = sum(1 for p in products if p.status == "en_ligne")
    pending_products = sum(1 for p in products if p.status == "en_attente")

    # If new agent with 0 records, give baseline stats as mockups show or actual count
    total_commerces = max(commerces_count, len(surveys))
    total_products = len(products)
    pending_total = pending_commerces + pending_products

    return {
        "commerces": total_commerces,
        "products": total_products,
        "pending": pending_total,
        "total_surveys": len(surveys),
        "verified": commerces_count,
        "verification_score": surveyor.verification_score or 4.9,
        "last_sync": surveyor.last_sync,
        "sync_status": surveyor.sync_status
    }


@router.get("/recent-activity")
async def get_recent_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get surveyor's recent actions for 'Aujourd'hui' section on Dashboard"""
    surveyor = await _get_or_create_surveyor(db, current_user)

    # 1. Recent Surveys/Commerces
    s_query = select(Survey, Category.name.label("category_name")).join(
        Category, Survey.category_id == Category.id, isouter=True
    ).where(Survey.surveyor_id == surveyor.id).order_by(desc(Survey.created_at)).limit(6)
    s_res = await db.execute(s_query)
    survey_rows = s_res.all()

    activities = []
    for s, cat_name in survey_rows:
        # Get first photo if exists
        p_res = await db.execute(select(SurveyPhoto.photo_url).where(SurveyPhoto.survey_id == s.id).limit(1))
        photo_url = p_res.scalar_one_or_none()

        activities.append({
            "id": s.id,
            "commerce_id": s.commerce_id,
            "title": s.store_name,
            "type": "commerce",
            "category": cat_name or "Commerce",
            "subtitle": f"{cat_name or 'Commerce'} • {'Enregistré' if s.status != 'pending' else 'En attente'}",
            "status": "enregistre" if s.status != "pending" else "en_attente",
            "is_verified": s.status != "pending",
            "photo_url": photo_url,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    # 2. Recent Products
    p_query = select(Product, Commerce.name.label("commerce_name")).join(
        Commerce, Product.commerce_id == Commerce.id, isouter=True
    ).where(Product.created_by == current_user.id).order_by(desc(Product.created_at)).limit(6)
    p_res = await db.execute(p_query)
    prod_rows = p_res.all()

    for p, c_name in prod_rows:
        activities.append({
            "id": p.id,
            "commerce_id": p.commerce_id,
            "title": p.name,
            "type": "product",
            "category": p.category or "Produit",
            "subtitle": f"Produit • {'Enregistré' if p.status == 'en_ligne' else 'En attente'}",
            "status": "enregistre" if p.status == "en_ligne" else "en_attente",
            "is_verified": p.status == "en_ligne",
            "photo_url": p.cover_photo or (p.photos[0] if p.photos else None),
            "created_at": p.created_at.isoformat() if p.created_at else None
        })

    # Sort combined activities by created_at desc
    activities.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    return activities[:10]


@router.post("/surveys")
async def create_survey(
    data: SurveyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new store survey AND simultaneously create an active Commerce
    so the surveyed business is IMMEDIATELY available in YAAR+ public app!
    """
    surveyor = await _get_or_create_surveyor(db, current_user)

    # 1. Get or create merchant profile for the owner/agent
    m_res = await db.execute(select(Merchant).where(Merchant.user_id == current_user.id))
    merchant = m_res.scalar_one_or_none()
    if not merchant:
        merchant = Merchant(
            user_id=current_user.id,
            business_name=data.owner_name or data.store_name,
            is_verified=True,
            rating_avg=4.5,
            total_reviews=1
        )
        db.add(merchant)
        await db.flush()

    # 2. Extract photos
    photo_urls = [p.photo_url for p in data.photos]
    cover_photo = data.cover_photo or (photo_urls[0] if photo_urls else None)

    # 2.5 Resilient Category resolution
    real_cat_id = data.category_id
    cat_res = await db.execute(select(Category).where(Category.id == data.category_id))
    cat = cat_res.scalar_one_or_none()
    if not cat:
        search_term = (data.category_id or "").strip()
        cat_by_name = await db.execute(
            select(Category).where(
                Category.name.ilike(f"%{search_term}%") | Category.slug.ilike(f"%{search_term}%")
            )
        )
        matched_cat = cat_by_name.scalar_one_or_none()
        if matched_cat:
            real_cat_id = matched_cat.id
        else:
            first_cat = (await db.execute(select(Category).limit(1))).scalar_one_or_none()
            if first_cat:
                real_cat_id = first_cat.id

    # 3. Create active Commerce
    slug_base = _slugify(data.store_name)
    slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

    commerce = Commerce(
        merchant_id=merchant.id,
        category_id=real_cat_id,
        name=data.store_name,
        slug=slug,
        description=data.description or f"Commerce recensé à {data.city or 'Ouagadougou'}",
        phone=data.phone,
        whatsapp=data.whatsapp or data.phone,
        address=data.address,
        city=data.city or "Ouagadougou",
        quartier=data.quartier or "Secteur 12",
        latitude=data.latitude,
        longitude=data.longitude,
        cover_photo=cover_photo,
        photos=photo_urls,
        opening_hours=data.opening_hours.model_dump() if data.opening_hours else {"mon": ["07:00", "19:00"], "tue": ["07:00", "19:00"], "wed": ["07:00", "19:00"], "thu": ["07:00", "19:00"], "fri": ["07:00", "19:00"], "sat": ["07:00", "19:00"], "sun": ["07:00", "19:00"]},
        is_open_now=True,
        services=data.services or [],
        tags=data.tags or [],
        status=CommerceStatus.ACTIVE,  # ACTIVE: immediately available in public YAAR+!
        is_featured=False,
        rating_avg=4.5,
        total_reviews=0
    )
    db.add(commerce)
    await db.flush()

    # 4. Create Survey record
    survey = Survey(
        surveyor_id=surveyor.id,
        commerce_id=commerce.id,
        store_name=data.store_name,
        owner_name=data.owner_name or data.store_name,
        category_id=data.category_id,
        subcategory_id=data.subcategory_id,
        phone=data.phone,
        address=data.address,
        city=data.city or "Ouagadougou",
        quartier=data.quartier,
        latitude=data.latitude,
        longitude=data.longitude,
        gps_accuracy=data.gps_accuracy,
        description=data.description,
        opening_hours=data.opening_hours.model_dump() if data.opening_hours else None,
        services=data.services or [],
        tags=data.tags or [],
        status="verified",
        is_active=True,
        survey_date=datetime.utcnow()
    )
    db.add(survey)
    await db.flush()

    # Add SurveyPhotos
    for photo_url in photo_urls:
        photo = SurveyPhoto(
            survey_id=survey.id,
            photo_url=photo_url,
            photo_type="storefront"
        )
        db.add(photo)

    surveyor.total_stores_surveyed += 1
    await db.commit()
    await db.refresh(survey)
    await db.refresh(commerce)

    return {
        "id": survey.id,
        "commerce_id": commerce.id,
        "store_name": commerce.name,
        "category_id": commerce.category_id,
        "phone": commerce.phone,
        "address": commerce.address,
        "latitude": commerce.latitude,
        "longitude": commerce.longitude,
        "status": "verified",
        "commerce": {
            "id": commerce.id,
            "name": commerce.name,
            "cover_photo": commerce.cover_photo,
            "phone": commerce.phone,
            "whatsapp": commerce.whatsapp,
            "address": commerce.address,
            "latitude": commerce.latitude,
            "longitude": commerce.longitude,
            "status": commerce.status
        }
    }


@router.get("/commerces")
async def list_surveyor_commerces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = None,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100)
):
    """List agent's surveyed commerces (Mes commerces)"""
    surveyor = await _get_or_create_surveyor(db, current_user)

    query = select(Survey, Commerce, Category.name.label("category_name")).join(
        Commerce, Survey.commerce_id == Commerce.id, isouter=True
    ).join(
        Category, Survey.category_id == Category.id, isouter=True
    ).where(Survey.surveyor_id == surveyor.id)

    if status and status != "Tous":
        if status.lower() == "publié":
            query = query.where(Survey.status.in_(["verified", "active"]))
        elif status.lower() == "en attente":
            query = query.where(Survey.status == "pending")

    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Survey.store_name).like(search_term),
                func.lower(Survey.address).like(search_term),
                func.lower(Category.name).like(search_term),
            )
        )

    query = query.order_by(desc(Survey.created_at)).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for s, c, cat_name in rows:
        # Get cover photo
        p_res = await db.execute(select(SurveyPhoto.photo_url).where(SurveyPhoto.survey_id == s.id).limit(1))
        photo_url = p_res.scalar_one_or_none() or (c.cover_photo if c else None)

        items.append({
            "id": s.id,
            "commerce_id": s.commerce_id,
            "name": s.store_name,
            "category": cat_name or "Commerce",
            "address": s.address or f"{s.city}, {s.quartier or 'Centre'}",
            "phone": s.phone,
            "status": "Publié" if s.status != "pending" else "En attente",
            "photo_url": photo_url,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    return items


@router.post("/batch-sync")
async def batch_sync_surveys(
    surveys_data: List[SurveyCreate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Batch sync multiple offline surveys with automatic live commerce activation"""
    surveyor = await _get_or_create_surveyor(db, current_user)

    m_res = await db.execute(select(Merchant).where(Merchant.user_id == current_user.id))
    merchant = m_res.scalar_one_or_none()
    if not merchant:
        merchant = Merchant(user_id=current_user.id, business_name=current_user.full_name, is_verified=True)
        db.add(merchant)
        await db.flush()

    synced_count = 0
    for survey_data in surveys_data:
        photo_urls = [p.photo_url for p in survey_data.photos]
        cover_photo = survey_data.cover_photo or (photo_urls[0] if photo_urls else None)

        # Resilient category resolution
        real_cat_id = survey_data.category_id
        cat_res = await db.execute(select(Category).where(Category.id == survey_data.category_id))
        cat = cat_res.scalar_one_or_none()
        if not cat:
            search_term = (survey_data.category_id or "").strip()
            cat_by_name = await db.execute(
                select(Category).where(
                    Category.name.ilike(f"%{search_term}%") | Category.slug.ilike(f"%{search_term}%")
                )
            )
            matched_cat = cat_by_name.scalar_one_or_none()
            if matched_cat:
                real_cat_id = matched_cat.id
            else:
                first_cat = (await db.execute(select(Category).limit(1))).scalar_one_or_none()
                if first_cat:
                    real_cat_id = first_cat.id

        commerce = Commerce(
            merchant_id=merchant.id,
            category_id=real_cat_id,
            name=survey_data.store_name,
            slug=f"{_slugify(survey_data.store_name)}-{uuid.uuid4().hex[:6]}",
            description=survey_data.description,
            phone=survey_data.phone,
            whatsapp=survey_data.whatsapp or survey_data.phone,
            address=survey_data.address,
            city=survey_data.city or "Ouagadougou",
            quartier=survey_data.quartier or "Secteur 12",
            latitude=survey_data.latitude,
            longitude=survey_data.longitude,
            cover_photo=cover_photo,
            photos=photo_urls,
            services=survey_data.services or [],
            status=CommerceStatus.ACTIVE,
            is_open_now=True
        )
        db.add(commerce)
        await db.flush()

        survey = Survey(
            surveyor_id=surveyor.id,
            commerce_id=commerce.id,
            store_name=survey_data.store_name,
            owner_name=survey_data.owner_name or survey_data.store_name,
            category_id=survey_data.category_id,
            phone=survey_data.phone,
            address=survey_data.address,
            city=survey_data.city or "Ouagadougou",
            latitude=survey_data.latitude,
            longitude=survey_data.longitude,
            status="verified",
            survey_date=datetime.utcnow()
        )
        db.add(survey)
        synced_count += 1

    surveyor.last_sync = datetime.utcnow()
    surveyor.sync_status = "synced"
    surveyor.total_stores_surveyed += synced_count
    await db.commit()

    return {
        "status": "synced",
        "synced_count": synced_count,
        "last_sync": surveyor.last_sync
    }
