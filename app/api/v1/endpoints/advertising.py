from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, or_
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User, UserRole, Commerce, PromotionalOffer, Advertisement,
    AdvertisementSpot
)
from app.schemas.schemas import (
    PromotionalOfferCreate, PromotionalOfferResponse,
    AdvertisementSpotResponse, PaginationResponse
)

router = APIRouter(prefix="/advertising", tags=["Advertising"])


# ── Promotional Offers ─────────────────────────────────────────────────────────

@router.post("/offers", response_model=PromotionalOfferResponse)
async def create_promotional_offer(
    commerce_id: str,
    data: PromotionalOfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a promotional offer for a commerce"""
    result = await db.execute(
        select(Commerce).where(Commerce.id == commerce_id)
    )
    commerce = result.scalar_one_or_none()
    if not commerce:
        raise HTTPException(status_code=404, detail="Commerce not found")

    # Check authorization
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AD_MANAGER]:
        if commerce.merchant_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    offer = PromotionalOffer(
        commerce_id=commerce_id,
        title=data.title,
        description=data.description,
        image_url=data.image_url,
        discount_percent=data.discount_percent,
        discount_amount_fcfa=data.discount_amount_fcfa,
        code=data.code,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        is_active=True
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


@router.get("/offers", response_model=PaginationResponse)
async def list_offers(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    commerce_id: Optional[str] = None,
    active_only: bool = True
):
    """List promotional offers"""
    query = select(PromotionalOffer)

    if active_only:
        query = query.where(
            and_(
                PromotionalOffer.is_active == True,
                PromotionalOffer.ends_at > datetime.utcnow()
            )
        )

    if commerce_id:
        query = query.where(PromotionalOffer.commerce_id == commerce_id)

    # Count total
    result = await db.execute(select(PromotionalOffer))
    total = len(result.scalars().all())

    # Get paginated results
    result = await db.execute(
        query.order_by(desc(PromotionalOffer.starts_at))
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


@router.get("/offers/{offer_id}", response_model=PromotionalOfferResponse)
async def get_offer(
    offer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get offer details"""
    result = await db.execute(
        select(PromotionalOffer).where(PromotionalOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.put("/offers/{offer_id}", response_model=PromotionalOfferResponse)
async def update_offer(
    offer_id: str,
    data: PromotionalOfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update promotional offer"""
    result = await db.execute(
        select(PromotionalOffer).where(PromotionalOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    # Check authorization
    commerce_result = await db.execute(
        select(Commerce).where(Commerce.id == offer.commerce_id)
    )
    commerce = commerce_result.scalar()

    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AD_MANAGER]:
        if commerce.merchant_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    offer.title = data.title
    offer.description = data.description
    offer.image_url = data.image_url
    offer.discount_percent = data.discount_percent
    offer.discount_amount_fcfa = data.discount_amount_fcfa
    offer.starts_at = data.starts_at
    offer.ends_at = data.ends_at
    await db.commit()
    await db.refresh(offer)
    return offer


@router.delete("/offers/{offer_id}")
async def delete_offer(
    offer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete promotional offer"""
    result = await db.execute(
        select(PromotionalOffer).where(PromotionalOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    commerce_result = await db.execute(
        select(Commerce).where(Commerce.id == offer.commerce_id)
    )
    commerce = commerce_result.scalar()

    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AD_MANAGER]:
        if commerce.merchant_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(offer)
    await db.commit()
    return {"status": "deleted"}


@router.post("/offers/{offer_id}/view")
async def track_offer_view(
    offer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Track offer view"""
    result = await db.execute(
        select(PromotionalOffer).where(PromotionalOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    offer.view_count += 1
    await db.commit()
    return {"view_count": offer.view_count}


@router.post("/offers/{offer_id}/click")
async def track_offer_click(
    offer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Track offer click"""
    result = await db.execute(
        select(PromotionalOffer).where(PromotionalOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    offer.click_count += 1
    await db.commit()
    return {"click_count": offer.click_count}


# ── Advertisement Spots ────────────────────────────────────────────────────────

@router.get("/spots", response_model=List[AdvertisementSpotResponse])
async def list_ad_spots(
    db: AsyncSession = Depends(get_db),
    placement: Optional[str] = None,
    available_only: bool = False
):
    """List advertisement spots"""
    query = select(AdvertisementSpot)
    if placement:
        query = query.where(AdvertisementSpot.placement == placement)
    if available_only:
        query = query.where(AdvertisementSpot.is_available == True)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/spots")
async def create_ad_spot(
    placement: str,
    position: int,
    width: int = 360,
    height: int = 200,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create advertisement spot (admin only)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AD_MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")

    spot = AdvertisementSpot(
        placement=placement,
        position=position,
        width=width,
        height=height,
        is_available=True
    )
    db.add(spot)
    await db.commit()
    await db.refresh(spot)
    return spot


# ── Nearby Promotions ──────────────────────────────────────────────────────────

@router.get("/nearby-promotions")
async def get_nearby_promotions(
    latitude: float,
    longitude: float,
    radius_km: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """Get promotions near user location"""
    from sqlalchemy import func

    # Simple distance calculation (rough approximation)
    # More precise geo queries would use PostGIS
    result = await db.execute(
        select(PromotionalOffer)
        .join(Commerce)
        .where(
            and_(
                PromotionalOffer.is_active == True,
                PromotionalOffer.ends_at > datetime.utcnow(),
                func.sqrt(
                    (Commerce.latitude - latitude) ** 2 +
                    (Commerce.longitude - longitude) ** 2
                ) * 111 < radius_km  # Rough approximation: 1 degree ≈ 111 km
            )
        )
        .order_by(desc(PromotionalOffer.view_count))
        .limit(20)
    )
    promotions = result.scalars().all()

    return {
        "promotions": promotions,
        "count": len(promotions),
        "radius_km": radius_km
    }


@router.get("/featured-commerces")
async def get_featured_commerces(
    db: AsyncSession = Depends(get_db),
    limit: int = 10
):
    """Get featured/sponsored commerces"""
    result = await db.execute(
        select(Commerce)
        .where(
            or_(
                Commerce.is_featured == True,
                Commerce.is_premium_listing == True
            )
        )
        .order_by(desc(Commerce.view_count))
        .limit(limit)
    )
    commerces = result.scalars().all()
    return {"featured_commerces": commerces}
