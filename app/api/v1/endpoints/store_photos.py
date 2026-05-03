from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Commerce, StorePhoto
from app.schemas.schemas import StorePhotoCreate, StorePhotoResponse, PaginationResponse

router = APIRouter(prefix="/commerces/{commerce_id}/photos", tags=["Store Photos"])


@router.post("", response_model=StorePhotoResponse)
async def add_store_photo(
    commerce_id: str,
    data: StorePhotoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a photo to a store"""
    result = await db.execute(
        select(Commerce).where(Commerce.id == commerce_id)
    )
    commerce = result.scalar_one_or_none()
    if not commerce:
        raise HTTPException(status_code=404, detail="Commerce not found")

    # Check authorization
    merchant_result = await db.execute(
        select(Commerce).where(
            Commerce.id == commerce_id,
            Commerce.merchant_id == current_user.id
        )
    )
    if not merchant_result.scalar() and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # If this is the first cover photo, set it as cover
    if data.is_cover:
        await db.execute(
            select(StorePhoto).where(
                StorePhoto.commerce_id == commerce_id,
                StorePhoto.is_cover == True
            )
        )
        # Set previous cover to False
        existing_covers = (await db.execute(
            select(StorePhoto).where(
                StorePhoto.commerce_id == commerce_id,
                StorePhoto.is_cover == True
            )
        )).scalars().all()
        for cover in existing_covers:
            cover.is_cover = False

    # Get max display order
    result = await db.execute(
        select(StorePhoto).where(StorePhoto.commerce_id == commerce_id)
    )
    photos = result.scalars().all()
    max_order = max([p.display_order for p in photos], default=-1)

    photo = StorePhoto(
        commerce_id=commerce_id,
        photo_url=data.photo_url,
        photo_type=data.photo_type,
        is_cover=data.is_cover,
        display_order=max_order + 1,
        uploaded_by=current_user.id
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


@router.get("", response_model=List[StorePhotoResponse])
async def list_store_photos(
    commerce_id: str,
    db: AsyncSession = Depends(get_db),
    photo_type: str = None
):
    """List all photos for a store"""
    result = await db.execute(
        select(Commerce).where(Commerce.id == commerce_id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="Commerce not found")

    query = select(StorePhoto).where(
        StorePhoto.commerce_id == commerce_id
    )
    if photo_type:
        query = query.where(StorePhoto.photo_type == photo_type)

    result = await db.execute(
        query.order_by(StorePhoto.display_order)
    )
    return result.scalars().all()


@router.get("/{photo_id}", response_model=StorePhotoResponse)
async def get_store_photo(
    commerce_id: str,
    photo_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific photo"""
    result = await db.execute(
        select(StorePhoto).where(
            StorePhoto.id == photo_id,
            StorePhoto.commerce_id == commerce_id
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


@router.put("/{photo_id}", response_model=StorePhotoResponse)
async def update_store_photo(
    commerce_id: str,
    photo_id: str,
    data: StorePhotoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a photo"""
    result = await db.execute(
        select(StorePhoto).where(
            StorePhoto.id == photo_id,
            StorePhoto.commerce_id == commerce_id
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Check authorization
    commerce_result = await db.execute(
        select(Commerce).where(Commerce.id == commerce_id)
    )
    commerce = commerce_result.scalar()

    if current_user.role not in ["admin", "super_admin"]:
        if photo.uploaded_by != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    if data.is_cover:
        # Remove cover from other photos
        existing_covers = (await db.execute(
            select(StorePhoto).where(
                StorePhoto.commerce_id == commerce_id,
                StorePhoto.is_cover == True,
                StorePhoto.id != photo_id
            )
        )).scalars().all()
        for cover in existing_covers:
            cover.is_cover = False

    photo.photo_url = data.photo_url
    photo.photo_type = data.photo_type
    photo.is_cover = data.is_cover
    await db.commit()
    await db.refresh(photo)
    return photo


@router.delete("/{photo_id}")
async def delete_store_photo(
    commerce_id: str,
    photo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a photo"""
    result = await db.execute(
        select(StorePhoto).where(
            StorePhoto.id == photo_id,
            StorePhoto.commerce_id == commerce_id
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if current_user.role not in ["admin", "super_admin"]:
        if photo.uploaded_by != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(photo)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{photo_id}/set-cover")
async def set_as_cover(
    commerce_id: str,
    photo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Set a photo as cover photo"""
    result = await db.execute(
        select(StorePhoto).where(
            StorePhoto.id == photo_id,
            StorePhoto.commerce_id == commerce_id
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Remove cover from other photos
    existing_covers = (await db.execute(
        select(StorePhoto).where(
            StorePhoto.commerce_id == commerce_id,
            StorePhoto.is_cover == True,
            StorePhoto.id != photo_id
        )
    )).scalars().all()
    for cover in existing_covers:
        cover.is_cover = False

    photo.is_cover = True
    await db.commit()
    return {"status": "cover_set"}


@router.post("/{photo_id}/reorder")
async def reorder_photo(
    commerce_id: str,
    photo_id: str,
    new_order: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reorder photos"""
    result = await db.execute(
        select(StorePhoto).where(
            StorePhoto.id == photo_id,
            StorePhoto.commerce_id == commerce_id
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.display_order = new_order
    await db.commit()
    return {"status": "reordered"}
