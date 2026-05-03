from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_, String
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from math import radians, sin, cos, sqrt, atan2
import re
import unicodedata

from app.models.models import Commerce, Category, CommerceStatus
from app.schemas.schemas import CommerceCreate, CommerceUpdate, NearbySearchRequest
from slugify import slugify


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two GPS points"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def normalize_search_text(value: str | None) -> str:
    return unicodedata.normalize("NFD", value or "") \
        .encode("ascii", "ignore") \
        .decode("ascii") \
        .lower() \
        .strip()


def split_search_terms(value: str | None) -> List[str]:
    normalized = normalize_search_text(value)
    if not normalized:
        return []
    terms = re.split(r"\s+", normalized)
    return [term for term in terms if len(term) >= 3]


class CommerceService:

    @staticmethod
    async def create_commerce(db: AsyncSession, merchant_id: str, data: CommerceCreate) -> Commerce:
        slug_base = slugify(data.name)
        slug = slug_base
        counter = 1
        while True:
            existing = await db.execute(select(Commerce).where(Commerce.slug == slug))
            if not existing.scalar_one_or_none():
                break
            slug = f"{slug_base}-{counter}"
            counter += 1

        commerce = Commerce(
            merchant_id=merchant_id,
            category_id=data.category_id,
            name=data.name,
            slug=slug,
            description=data.description,
            phone=data.phone,
            whatsapp=data.whatsapp,
            address=data.address,
            city=data.city,
            quartier=data.quartier,
            latitude=data.latitude,
            longitude=data.longitude,
            opening_hours=data.opening_hours.model_dump() if data.opening_hours else None,
            tags=data.tags,
            services=data.services,
        )
        db.add(commerce)
        await db.flush()
        return commerce

    @staticmethod
    async def get_by_id(db: AsyncSession, commerce_id: str) -> Optional[Commerce]:
        result = await db.execute(
            select(Commerce)
            .where(Commerce.id == commerce_id)
            .options()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_nearby(
        db: AsyncSession,
        req: NearbySearchRequest,
        is_premium: bool = False,
    ) -> Tuple[List[dict], int]:
        """
        Geo search using bounding box + haversine filter.
        Returns list of commerce dicts with distance.
        """
        # Bounding box approximation for initial DB filter
        km_per_degree_lat = 111.0
        km_per_degree_lon = 111.0 * cos(radians(req.latitude))
        lat_delta = req.radius_km / km_per_degree_lat
        lon_delta = req.radius_km / km_per_degree_lon

        min_lat = req.latitude - lat_delta
        max_lat = req.latitude + lat_delta
        min_lon = req.longitude - lon_delta
        max_lon = req.longitude + lon_delta

        query = (
            select(Commerce)
            .where(
                Commerce.status == CommerceStatus.ACTIVE,
                Commerce.latitude.between(min_lat, max_lat),
                Commerce.longitude.between(min_lon, max_lon),
            )
            .options(selectinload(Commerce.category))
        )

        if req.category_slug:
            cat_result = await db.execute(
                select(Category).where(Category.slug == req.category_slug)
            )
            cat = cat_result.scalar_one_or_none()
            if cat:
                query = query.where(Commerce.category_id == cat.id)

        if req.open_now:
            query = query.where(Commerce.is_open_now == True)

        # Over-fetch because query text and distance are finalized in Python.
        query = query.limit(max(req.limit * 20, 200))
        result = await db.execute(query)
        commerces = result.scalars().all()

        # Calculate real distances and sort
        items = []
        normalized_query = normalize_search_text(req.query)
        query_terms = split_search_terms(req.query)
        for c in commerces:
            dist = haversine_distance(req.latitude, req.longitude, c.latitude, c.longitude)
            if dist > req.radius_km:
                continue

            if normalized_query:
                search_blob = " ".join([
                    c.name or "",
                    c.description or "",
                    c.quartier or "",
                    " ".join(c.tags or []),
                    " ".join(c.services or []),
                    c.category.name if c.category else "",
                    c.category.slug if c.category else "",
                ])
                normalized_blob = normalize_search_text(search_blob)
                if normalized_query not in normalized_blob:
                    matched_terms = [term for term in query_terms if term in normalized_blob]
                    if req.category_slug:
                        if not matched_terms:
                            continue
                    else:
                        minimum_matches = 1 if len(query_terms) <= 1 else 2
                        if len(matched_terms) < minimum_matches:
                            continue

            items.append((c, dist))

        items.sort(key=lambda x: x[1])
        total = len(items)
        start = (req.page - 1) * req.limit
        end = start + req.limit
        items = items[start:end]

        result_list = []
        for commerce, dist in items:
            d = {
                "id": commerce.id,
                "name": commerce.name,
                "description": commerce.description,
                "address": commerce.address,
                "city": commerce.city,
                "quartier": commerce.quartier,
                "cover_photo": commerce.cover_photo,
                "photos": commerce.photos or [],
                "tags": commerce.tags or [],
                "rating_avg": commerce.rating_avg,
                "average_rating": commerce.rating_avg,
                "total_reviews": commerce.total_reviews,
                "review_count": commerce.total_reviews,
                "is_open_now": commerce.is_open_now,
                "is_open": commerce.is_open_now,
                "distance_km": round(dist, 2),
                "distance_meters": round(dist * 1000, 0),
                "category_id": commerce.category_id,
                "category_name": commerce.category.name if commerce.category else None,
                "category_slug": commerce.category.slug if commerce.category else None,
                "category_icon": commerce.category.icon if commerce.category else None,
            }
            d["latitude"] = commerce.latitude
            d["longitude"] = commerce.longitude
            d["opening_hours"] = commerce.opening_hours
            if is_premium:
                d["phone"] = commerce.phone
                d["whatsapp"] = commerce.whatsapp
            result_list.append(d)

        return result_list, total

    @staticmethod
    async def increment_view(db: AsyncSession, commerce_id: str):
        await db.execute(
            update(Commerce)
            .where(Commerce.id == commerce_id)
            .values(view_count=Commerce.view_count + 1)
        )

    @staticmethod
    async def approve_commerce(db: AsyncSession, commerce_id: str):
        await db.execute(
            update(Commerce)
            .where(Commerce.id == commerce_id)
            .values(status=CommerceStatus.ACTIVE)
        )

    @staticmethod
    async def reject_commerce(db: AsyncSession, commerce_id: str):
        await db.execute(
            update(Commerce)
            .where(Commerce.id == commerce_id)
            .values(status=CommerceStatus.REJECTED)
        )
