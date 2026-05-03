# users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.user_service import UserService
from app.schemas.schemas import UserResponse, UserUpdate, UserLocationUpdate
from app.models.models import Favorite, Commerce

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user=Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await UserService.update_user(db, current_user.id, data)


@router.post("/me/location")
async def update_location(
    data: UserLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import update
    from app.models.models import User
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(last_lat=data.latitude, last_lng=data.longitude)
    )
    return {"status": "ok"}


@router.get("/me/favorites")
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Fonctionnalité Premium requise")

    result = await db.execute(
        select(Favorite).where(Favorite.user_id == current_user.id)
    )
    favorites = result.scalars().all()
    return [{"commerce_id": f.commerce_id, "created_at": f.created_at} for f in favorites]


@router.post("/me/favorites/{commerce_id}")
async def add_favorite(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Fonctionnalité Premium requise")

    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.commerce_id == commerce_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Déjà dans les favoris"}

    fav = Favorite(user_id=current_user.id, commerce_id=commerce_id)
    db.add(fav)
    return {"message": "Ajouté aux favoris"}


@router.delete("/me/favorites/{commerce_id}")
async def remove_favorite(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.commerce_id == commerce_id,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
    return {"message": "Retiré des favoris"}
