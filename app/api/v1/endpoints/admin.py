from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from datetime import datetime, timedelta, timezone
import re
import unicodedata

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.models import (
    User, Commerce, Merchant, Subscription, Category, Event,
    Advertisement, SupportTicket, CommerceStatus, SubscriptionStatus,
    Favorite, Review, StorePhoto, PromotionalOffer, Survey
)
from app.schemas.schemas import AdminCommerceCreate, AdminCommerceImportRequest, CommerceCreate

router = APIRouter()


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = unicodedata.normalize("NFKC", value).strip()
    cp1252_safe = normalized.encode("cp1252", errors="ignore").decode("cp1252")
    collapsed = re.sub(r"\s+", " ", cp1252_safe).strip()
    return collapsed or None


def _sanitize_phone(value: str | None) -> str | None:
    text = _sanitize_text(value)
    if not text:
        return None

    compact = re.sub(r"\s+", " ", text)
    if len(compact) <= 20:
        return compact

    match = re.search(r"\+?\d[\d\s\-()]{7,19}", compact)
    if match:
        candidate = re.sub(r"\s+", " ", match.group(0)).strip()
        if len(candidate) <= 20:
            return candidate
        compact = candidate

    return compact[:20].strip() or None


def _sanitize_import_payload(item):
    return {
        "name": _sanitize_text(item.name),
        "description": _sanitize_text(item.description),
        "phone": _sanitize_phone(item.phone),
        "whatsapp": _sanitize_phone(item.whatsapp),
        "address": _sanitize_text(item.address),
        "city": _sanitize_text(item.city),
        "quartier": _sanitize_text(item.quartier),
        "tags": [_sanitize_text(tag) for tag in (item.tags or []) if _sanitize_text(tag)],
        "services": [_sanitize_text(service) for service in (item.services or []) if _sanitize_text(service)],
    }


def _require_coordinates(latitude: float | None, longitude: float | None) -> tuple[float, float]:
    if latitude is None or longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Coordonnées GPS manquantes. Importez un fichier avec latitude et longitude réelles.",
        )

    return latitude, longitude


async def _get_or_create_admin_merchant(db: AsyncSession, user: User) -> Merchant:
    result = await db.execute(select(Merchant).where(Merchant.user_id == user.id))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant

    merchant = Merchant(
        user_id=user.id,
        business_name=user.full_name or "Catalogue admin YAAR+",
        is_verified=True,
    )
    db.add(merchant)
    await db.flush()
    return merchant


async def _ensure_category_exists(db: AsyncSession, category_id: str) -> Category:
    result = await db.execute(select(Category).where(Category.id == category_id, Category.is_active == True))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=400, detail="Catégorie invalide")
    return category


async def _find_existing_commerce(
    db: AsyncSession,
    name: str,
    city: str,
    address: str | None,
) -> Commerce | None:
    query = select(Commerce).where(
        func.lower(Commerce.name) == _normalize_text(name),
        func.lower(func.coalesce(Commerce.city, "")) == _normalize_text(city),
    )

    if address:
        query = query.where(func.lower(func.coalesce(Commerce.address, "")) == _normalize_text(address))

    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_premium = (await db.execute(select(func.count(User.id)).where(User.is_premium == True))).scalar() or 0
    total_merchants = (await db.execute(select(func.count(Merchant.id)))).scalar() or 0
    total_commerces = (await db.execute(select(func.count(Commerce.id)))).scalar() or 0
    pending_commerces = (await db.execute(
        select(func.count(Commerce.id)).where(Commerce.status == CommerceStatus.PENDING)
    )).scalar() or 0

    total_revenue = (await db.execute(
        select(func.sum(Subscription.price_fcfa)).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )).scalar() or 0

    monthly_revenue = (await db.execute(
        select(func.sum(Subscription.price_fcfa)).where(
            Subscription.starts_at >= month_start,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED]),
        )
    )).scalar() or 0

    return {
        "total_users": total_users,
        "total_premium_users": total_premium,
        "premium_rate": round(total_premium / total_users * 100, 1) if total_users else 0,
        "total_merchants": total_merchants,
        "total_commerces": total_commerces,
        "pending_commerces": pending_commerces,
        "total_revenue_fcfa": int(total_revenue),
        "monthly_revenue_fcfa": int(monthly_revenue),
    }


@router.get("/commerces/pending")
async def get_pending_commerces(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    offset = (page - 1) * limit
    result = await db.execute(
        select(Commerce)
        .where(Commerce.status == CommerceStatus.PENDING)
        .order_by(Commerce.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    commerces = result.scalars().all()
    total = (await db.execute(
        select(func.count(Commerce.id)).where(Commerce.status == CommerceStatus.PENDING)
    )).scalar() or 0

    return {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "address": c.address,
                "city": c.city,
                "quartier": c.quartier,
                "phone": c.phone,
                "status": c.status.value if c.status else None,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "created_at": c.created_at,
            }
            for c in commerces
        ],
        "total": total,
    }


@router.get("/commerces")
async def list_commerces(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    offset = (page - 1) * limit
    query = (
        select(Commerce, Category)
        .outerjoin(Category, Commerce.category_id == Category.id)
        .order_by(Commerce.created_at.desc())
    )

    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            Commerce.name.ilike(pattern)
            | Commerce.city.ilike(pattern)
            | Commerce.quartier.ilike(pattern)
        )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    result = await db.execute(query.offset(offset).limit(limit))
    rows = result.all()

    return {
        "items": [
            {
                "id": commerce.id,
                "name": commerce.name,
                "address": commerce.address,
                "city": commerce.city,
                "quartier": commerce.quartier,
                "phone": commerce.phone,
                "status": commerce.status.value if commerce.status else None,
                "category_name": category.name if category else "Non classé",
                "category_emoji": category.icon if category and category.icon else "🏪",
                "created_at": commerce.created_at,
            }
            for commerce, category in rows
        ],
        "total": total,
    }


@router.post("/commerces", status_code=201)
async def create_admin_commerce(
    payload: AdminCommerceCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    from app.services.commerce_service import CommerceService

    sanitized = _sanitize_import_payload(payload)
    if not sanitized["name"] or not sanitized["city"]:
        raise HTTPException(status_code=400, detail="Nom ou ville invalide")

    await _ensure_category_exists(db, payload.category_id)

    existing = await _find_existing_commerce(db, sanitized["name"], sanitized["city"], sanitized["address"])
    if existing:
        raise HTTPException(status_code=409, detail="Un commerce similaire existe déjà")

    merchant = await _get_or_create_admin_merchant(db, current_admin)
    latitude, longitude = _require_coordinates(payload.latitude, payload.longitude)

    commerce = await CommerceService.create_commerce(
        db,
        merchant.id,
        CommerceCreate(
            name=sanitized["name"],
            category_id=payload.category_id,
            description=sanitized["description"],
            phone=sanitized["phone"],
            whatsapp=sanitized["whatsapp"],
            address=sanitized["address"],
            city=sanitized["city"],
            quartier=sanitized["quartier"],
            latitude=latitude,
            longitude=longitude,
            opening_hours=payload.opening_hours,
            tags=sanitized["tags"],
            services=sanitized["services"],
        ),
    )
    commerce.status = CommerceStatus.ACTIVE  # ajout admin = toujours actif
    await db.commit()

    return {
        "id": commerce.id,
        "name": commerce.name,
        "status": commerce.status.value,
        "city": commerce.city,
        "used_fallback_coordinates": False,
        "message": "Commerce créé avec succès",
    }


@router.post("/commerces/import")
async def import_admin_commerces(
    payload: AdminCommerceImportRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    from app.services.commerce_service import CommerceService

    merchant = await _get_or_create_admin_merchant(db, current_admin)
    created = []
    skipped = []
    errors = []

    for index, item in enumerate(payload.items, start=1):
        try:
            async with db.begin_nested():
                sanitized = _sanitize_import_payload(item)
                if not sanitized["name"] or not sanitized["city"]:
                    raise HTTPException(status_code=400, detail="Nom ou ville invalide")

                await _ensure_category_exists(db, item.category_id)

                existing = await _find_existing_commerce(db, sanitized["name"], sanitized["city"], sanitized["address"])
                if existing:
                    skipped.append({
                        "row": item.source_row or index,
                        "name": sanitized["name"],
                        "reason": "duplicate",
                        "existing_id": existing.id,
                    })
                    continue

                latitude, longitude = _require_coordinates(item.latitude, item.longitude)
                commerce = await CommerceService.create_commerce(
                    db,
                    merchant.id,
                    CommerceCreate(
                        name=sanitized["name"],
                        category_id=item.category_id,
                        description=sanitized["description"],
                        phone=sanitized["phone"],
                        whatsapp=sanitized["whatsapp"],
                        address=sanitized["address"],
                        city=sanitized["city"],
                        quartier=sanitized["quartier"],
                        latitude=latitude,
                        longitude=longitude,
                        opening_hours=item.opening_hours,
                        tags=sanitized["tags"],
                        services=sanitized["services"],
                    ),
                )
                commerce.status = CommerceStatus.ACTIVE  # import admin = toujours actif
                await db.flush()  # s'assurer que le statut est bien écrit
                created.append({
                    "row": item.source_row or index,
                    "id": commerce.id,
                    "name": commerce.name,
                    "status": commerce.status.value,
                    "used_fallback_coordinates": False,
                })
        except HTTPException as exc:
            errors.append({
                "row": item.source_row or index,
                "name": _sanitize_text(item.name) or item.name,
                "detail": exc.detail,
            })
        except Exception as exc:
            errors.append({
                "row": item.source_row or index,
                "name": _sanitize_text(item.name) or item.name,
                "detail": str(exc),
            })

    await db.commit()

    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


@router.post("/commerces/clear-mine")
async def clear_my_admin_commerces(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    merchant_result = await db.execute(
        select(Merchant).where(Merchant.user_id == current_admin.id)
    )
    merchant = merchant_result.scalar_one_or_none()
    if not merchant:
        return {
            "deleted_count": 0,
            "message": "Aucun commerce admin à supprimer",
        }

    commerce_ids = (
        await db.execute(
            select(Commerce.id).where(Commerce.merchant_id == merchant.id)
        )
    ).scalars().all()

    if not commerce_ids:
        return {
            "deleted_count": 0,
            "message": "Aucun commerce admin à supprimer",
        }

    await db.execute(delete(Favorite).where(Favorite.commerce_id.in_(commerce_ids)))
    await db.execute(delete(Review).where(Review.commerce_id.in_(commerce_ids)))
    await db.execute(delete(StorePhoto).where(StorePhoto.commerce_id.in_(commerce_ids)))
    await db.execute(delete(PromotionalOffer).where(PromotionalOffer.commerce_id.in_(commerce_ids)))
    await db.execute(
        update(Advertisement)
        .where(Advertisement.commerce_id.in_(commerce_ids))
        .values(commerce_id=None)
    )
    await db.execute(
        update(Survey)
        .where(Survey.commerce_id.in_(commerce_ids))
        .values(commerce_id=None)
    )
    deleted_result = await db.execute(
        delete(Commerce).where(Commerce.id.in_(commerce_ids))
    )
    await db.commit()

    deleted_count = deleted_result.rowcount or len(commerce_ids)
    return {
        "deleted_count": deleted_count,
        "message": f"{deleted_count} commerce(s) supprimé(s)",
    }


@router.post("/commerces/{commerce_id}/approve")
async def approve_commerce(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    from app.services.commerce_service import CommerceService
    await CommerceService.approve_commerce(db, commerce_id)
    return {"message": "Commerce validé et publié"}


@router.post("/commerces/{commerce_id}/reject")
async def reject_commerce(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    from app.services.commerce_service import CommerceService
    await CommerceService.reject_commerce(db, commerce_id)
    return {"message": "Commerce rejeté"}


@router.post("/commerces/activate-all-pending")
async def activate_all_pending_commerces(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Active tous les commerces en attente en un clic."""
    result = await db.execute(
        update(Commerce)
        .where(Commerce.status == CommerceStatus.PENDING)
        .values(status=CommerceStatus.ACTIVE)
    )
    await db.commit()
    count = result.rowcount
    return {"activated_count": count, "message": f"{count} commerce(s) activé(s)"}


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    is_premium: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    query = select(User).order_by(User.created_at.desc())
    if is_premium is not None:
        query = query.where(User.is_premium == is_premium)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    users = result.scalars().all()

    return {
        "items": [
            {
                "id": u.id,
                "phone": u.phone,
                "full_name": u.full_name,
                "referral_code": u.referral_code,
                "is_premium": u.is_premium,
                "created_at": u.created_at,
            }
            for u in users
        ],
        "total": total,
    }


@router.post("/users/{user_id}/toggle-premium")
async def toggle_premium(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    new_status = not user.is_premium
    await db.execute(update(User).where(User.id == user_id).values(is_premium=new_status))
    return {"is_premium": new_status, "message": f"Premium {'activé' if new_status else 'désactivé'}"}


@router.get("/revenue/chart")
async def revenue_chart(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Daily revenue for the last N days"""
    from sqlalchemy import cast, Date
    start = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Subscription.created_at, Date).label("date"),
            func.sum(Subscription.price_fcfa).label("revenue"),
            func.count(Subscription.id).label("subscriptions"),
        )
        .where(Subscription.created_at >= start)
        .group_by(cast(Subscription.created_at, Date))
        .order_by(cast(Subscription.created_at, Date))
    )
    rows = result.all()
    return [
        {"date": str(r.date), "revenue": int(r.revenue), "subscriptions": r.subscriptions}
        for r in rows
    ]


@router.get("/subscriptions")
async def list_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    offset = (page - 1) * limit
    query = (
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .order_by(Subscription.created_at.desc())
    )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    result = await db.execute(query.offset(offset).limit(limit))
    rows = result.all()

    return {
        "items": [
            {
                "id": subscription.id,
                "user_name": user.full_name,
                "user_phone": user.phone,
                "plan": subscription.plan,
                "started_at": subscription.starts_at,
                "expires_at": subscription.expires_at,
                "amount": subscription.price_fcfa,
                "status": subscription.status.value if subscription.status else None,
            }
            for subscription, user in rows
        ],
        "total": total,
    }
