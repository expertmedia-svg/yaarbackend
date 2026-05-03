from fastapi import APIRouter
from sqlalchemy import select
from app.core.default_categories import ensure_default_categories
from app.core.database import get_db
from app.models.models import Category
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/")
async def list_categories(db: AsyncSession = Depends(get_db)):
    await ensure_default_categories(db)
    result = await db.execute(
        select(Category)
        .where(Category.is_active == True, Category.parent_id == None)
        .order_by(Category.sort_order)
    )
    categories = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "icon": c.icon,
            "color": c.color,
            "description": c.description,
        }
        for c in categories
    ]
