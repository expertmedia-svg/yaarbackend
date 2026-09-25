from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.services.commerce_service import CommerceService
from app.services.google_routes_service import GoogleRoutesService
from app.schemas.schemas import NearbySearchRequest, SearchResponse

router = APIRouter()


@router.get("/nearby")
@limiter.limit("60/minute")
async def search_nearby(
    request: Request,
    latitude: float = Query(..., description="Latitude GPS"),
    longitude: float = Query(..., description="Longitude GPS"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    category_slug: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    open_now: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
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
        db, req
    )

    return {
        "results": results,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total,
    }


@router.get("/autocomplete")
@limiter.limit("60/minute")
async def autocomplete(
    request: Request,
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
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


@router.get("/route-metrics")
@limiter.limit("20/minute")
async def route_metrics(
    request: Request,
    origin_lat: float = Query(..., description="Latitude du point de départ"),
    origin_lng: float = Query(..., description="Longitude du point de départ"),
    destination_lat: float = Query(..., description="Latitude de destination"),
    destination_lng: float = Query(..., description="Longitude de destination"),
):
    try:
        distance_meters, duration_minutes = await GoogleRoutesService.compute_driving_metrics(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            destination_lat=destination_lat,
            destination_lng=destination_lng,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Le calcul d'itineraire Google est indisponible pour le moment.",
        ) from exc

    return {
        "distance_meters": distance_meters,
        "distance_km": round(distance_meters / 1000, 2),
        "duration_minutes": duration_minutes,
    }
