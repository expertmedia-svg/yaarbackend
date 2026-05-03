from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.commerce_service import CommerceService
from app.schemas.schemas import NearbySearchRequest, SearchResponse

router = APIRouter()


@router.get("/nearby")
async def search_nearby(
    latitude: float = Query(..., description="Latitude GPS"),
    longitude: float = Query(..., description="Longitude GPS"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    category_slug: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    open_now: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    req = NearbySearchRequest(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        category_slug=category_slug,
        query=query,
        open_now=open_now,
        page=page,
        limit=limit,
    )

    results, total = await CommerceService.search_nearby(
        db, req, is_premium=current_user.is_premium or current_user.is_admin
    )

    return {
        "results": results,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total,
        "user_is_premium": current_user.is_premium,
    }


@router.get("/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Quick autocomplete for search bar"""
    from app.models.models import Commerce, CommerceStatus
    from sqlalchemy import select, func, or_

    query = (
        select(Commerce.id, Commerce.name, Commerce.city, Commerce.quartier)
        .where(
            Commerce.status == CommerceStatus.ACTIVE,
            or_(
                func.lower(Commerce.name).like(f"%{q.lower()}%"),
                func.lower(Commerce.quartier).like(f"%{q.lower()}%"),
            ),
        )
        .limit(8)
    )
    result = await db.execute(query)
    rows = result.all()
    return [
        {"id": r.id, "name": r.name, "city": r.city, "quartier": r.quartier}
        for r in rows
    ]
