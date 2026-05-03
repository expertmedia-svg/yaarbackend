from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, get_premium_user
from app.services.commerce_service import CommerceService
from app.schemas.schemas import CommerceCreate, CommerceUpdate, ReviewCreate, ReviewResponse
from app.models.models import Merchant, Review, Commerce, CommerceStatus
from sqlalchemy import select

router = APIRouter()


@router.post("/", status_code=201)
async def create_commerce(
    data: CommerceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Get or create merchant profile
    result = await db.execute(select(Merchant).where(Merchant.user_id == current_user.id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        merchant = Merchant(user_id=current_user.id, business_name=current_user.full_name)
        db.add(merchant)
        await db.flush()

    commerce = await CommerceService.create_commerce(db, merchant.id, data)
    return {
        "id": commerce.id,
        "slug": commerce.slug,
        "status": commerce.status,
        "message": "Commerce créé avec succès. En attente de validation.",
    }


@router.get("/{commerce_id}")
async def get_commerce(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    commerce = await CommerceService.get_by_id(db, commerce_id)
    if not commerce or commerce.status != CommerceStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="Commerce introuvable")

    await CommerceService.increment_view(db, commerce_id)

    # Load category
    from app.models.models import Category
    cat_result = await db.execute(select(Category).where(Category.id == commerce.category_id))
    category = cat_result.scalar_one_or_none()

    base = {
        "id": commerce.id,
        "name": commerce.name,
        "description": commerce.description,
        "address": commerce.address,
        "city": commerce.city,
        "quartier": commerce.quartier,
        "cover_photo": commerce.cover_photo,
        "photos": commerce.photos or [],
        "tags": commerce.tags or [],
        "services": commerce.services or [],
        "rating_avg": commerce.rating_avg,
        "total_reviews": commerce.total_reviews,
        "is_open_now": commerce.is_open_now,
        "category": {"id": category.id, "name": category.name, "icon": category.icon} if category else None,
        "category_name": category.name if category else None,
        "category_slug": category.slug if category else None,
        "category_icon": category.icon if category else None,
        "is_premium_content_locked": False,
        "phone": commerce.phone,
        "whatsapp": commerce.whatsapp,
        "latitude": commerce.latitude,
        "longitude": commerce.longitude,
        "opening_hours": commerce.opening_hours,
    }

    return base


@router.put("/{commerce_id}")
async def update_commerce(
    commerce_id: str,
    data: CommerceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    commerce = await CommerceService.get_by_id(db, commerce_id)
    if not commerce:
        raise HTTPException(status_code=404, detail="Commerce introuvable")

    # Check ownership
    result = await db.execute(select(Merchant).where(Merchant.user_id == current_user.id))
    merchant = result.scalar_one_or_none()
    if not merchant or commerce.merchant_id != merchant.id:
        raise HTTPException(status_code=403, detail="Non autorisé")

    update_data = data.model_dump(exclude_none=True)
    if "opening_hours" in update_data and data.opening_hours:
        update_data["opening_hours"] = data.opening_hours.model_dump()

    for key, value in update_data.items():
        setattr(commerce, key, value)

    return {"message": "Commerce mis à jour"}


@router.post("/{commerce_id}/reviews", status_code=201)
async def add_review(
    commerce_id: str,
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    commerce = await CommerceService.get_by_id(db, commerce_id)
    if not commerce:
        raise HTTPException(status_code=404, detail="Commerce introuvable")

    # Check no duplicate review
    existing = await db.execute(
        select(Review).where(Review.user_id == current_user.id, Review.commerce_id == commerce_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vous avez déjà noté ce commerce")

    review = Review(
        user_id=current_user.id,
        commerce_id=commerce_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)

    # Update commerce rating
    from sqlalchemy import func
    avg_result = await db.execute(
        select(func.avg(Review.rating)).where(Review.commerce_id == commerce_id)
    )
    new_avg = avg_result.scalar() or data.rating
    count_result = await db.execute(
        select(func.count(Review.id)).where(Review.commerce_id == commerce_id)
    )
    count = (count_result.scalar() or 0) + 1

    from sqlalchemy import update
    await db.execute(
        update(Commerce)
        .where(Commerce.id == commerce_id)
        .values(rating_avg=round(new_avg, 2), total_reviews=count)
    )

    return {"message": "Avis ajouté avec succès", "rating": data.rating}


@router.get("/{commerce_id}/reviews")
async def get_reviews(
    commerce_id: str,
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    result = await db.execute(
        select(Review)
        .where(Review.commerce_id == commerce_id)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reviews = result.scalars().all()
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at,
            "user_id": r.user_id,
        }
        for r in reviews
    ]
