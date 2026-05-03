from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, UserRole, Category, CategoryImage, Commerce
from app.schemas.schemas import CategoryResponseEnhanced, CategoryImageCreate

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponseEnhanced])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    parent_id: Optional[str] = None,
    is_active: bool = True
):
    """List all categories with images"""
    query = select(Category).where(Category.is_active == is_active)
    if parent_id:
        query = query.where(Category.parent_id == parent_id)
    else:
        query = query.where(Category.parent_id == None)

    result = await db.execute(query.order_by(Category.sort_order))
    categories = result.scalars().all()

    # Fetch images for each category
    response = []
    for cat in categories:
        img_result = await db.execute(
            select(CategoryImage).where(CategoryImage.category_id == cat.id)
            .order_by(CategoryImage.display_order)
        )
        images = img_result.scalars().all()
        cat_dict = {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "color": cat.color,
            "description": cat.description,
            "parent_id": cat.parent_id,
            "sort_order": cat.sort_order,
            "images": [
                {
                    "id": img.id,
                    "url": img.image_url,
                    "type": img.image_type,
                    "order": img.display_order
                }
                for img in images
            ]
        }
        response.append(cat_dict)

    return response


@router.get("/{category_id}", response_model=CategoryResponseEnhanced)
async def get_category(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get category with all images"""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    img_result = await db.execute(
        select(CategoryImage).where(CategoryImage.category_id == category_id)
        .order_by(CategoryImage.display_order)
    )
    images = img_result.scalars().all()

    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "icon": category.icon,
        "color": category.color,
        "description": category.description,
        "parent_id": category.parent_id,
        "sort_order": category.sort_order,
        "images": [
            {
                "id": img.id,
                "url": img.image_url,
                "type": img.image_type,
                "order": img.display_order
            }
            for img in images
        ]
    }


@router.get("/{category_id}/commerces")
async def get_category_commerces(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get all commerces in a category"""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="Category not found")

    commerce_result = await db.execute(
        select(Commerce)
        .where(Commerce.category_id == category_id)
        .offset(skip)
        .limit(limit)
    )
    commerces = commerce_result.scalars().all()

    return {
        "category_id": category_id,
        "commerces": commerces,
        "count": len(commerces)
    }


@router.post("/{category_id}/images")
async def add_category_image(
    category_id: str,
    data: CategoryImageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add image to category (admin only)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MARKETING]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="Category not found")

    image = CategoryImage(
        category_id=category_id,
        image_url=data.image_url,
        image_type=data.image_type,
        display_order=data.display_order
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    return {
        "id": image.id,
        "image_url": image.image_url,
        "image_type": image.image_type,
        "display_order": image.display_order
    }


@router.put("/{category_id}/images/{image_id}")
async def update_category_image(
    category_id: str,
    image_id: str,
    data: CategoryImageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update category image"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MARKETING]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(CategoryImage).where(
            and_(
                CategoryImage.id == image_id,
                CategoryImage.category_id == category_id
            )
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    image.image_url = data.image_url
    image.image_type = data.image_type
    image.display_order = data.display_order
    await db.commit()
    await db.refresh(image)

    return {
        "id": image.id,
        "image_url": image.image_url,
        "image_type": image.image_type,
        "display_order": image.display_order
    }


@router.delete("/{category_id}/images/{image_id}")
async def delete_category_image(
    category_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete category image"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MARKETING]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(CategoryImage).where(
            and_(
                CategoryImage.id == image_id,
                CategoryImage.category_id == category_id
            )
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    await db.delete(image)
    await db.commit()
    return {"status": "deleted"}
