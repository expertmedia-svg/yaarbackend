from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Category


DEFAULT_CATEGORIES = [
    {"name": "Restaurants & Maquis", "slug": "restaurants", "icon": "utensils", "color": "#E8621A"},
    {"name": "Boulangeries", "slug": "boulangeries", "icon": "bread", "color": "#F5A623"},
    {"name": "Pharmacies", "slug": "pharmacies", "icon": "pill", "color": "#2ECC71"},
    {"name": "Épiceries & Boutiques", "slug": "epiceries-boutiques", "icon": "cart", "color": "#3498DB"},
    {"name": "Fruits & Légumes", "slug": "fruits-legumes", "icon": "leaf", "color": "#27AE60"},
    {"name": "Gaz & Énergie", "slug": "gaz-energie", "icon": "fuel", "color": "#E74C3C"},
    {"name": "Garages & Mécanique", "slug": "garages-mecaniques", "icon": "wrench", "color": "#95A5A6"},
    {"name": "Coiffure & Beauté", "slug": "coiffure-beaute", "icon": "scissors", "color": "#E91E63"},
    {"name": "Pressing & Laverie", "slug": "pressing-laverie", "icon": "shirt", "color": "#9B59B6"},
    {"name": "Artisans", "slug": "artisans", "icon": "hammer", "color": "#E67E22"},
    {"name": "Condiments & Épices", "slug": "condiments-epices", "icon": "pepper", "color": "#E74C3C"},
    {"name": "Kiosques", "slug": "kiosques", "icon": "store", "color": "#16A085"},
    {"name": "Événements Locaux", "slug": "evenements-locaux", "icon": "calendar", "color": "#8E44AD"},
    {"name": "Marchés Alimentaires", "slug": "marche-alimentaire", "icon": "shopping-bag", "color": "#D35400"},
    {"name": "Autres Commerces", "slug": "autres-commerces", "icon": "grid", "color": "#7F8C8D"},
]


async def ensure_default_categories(db: AsyncSession) -> None:
    result = await db.execute(select(Category.id).limit(1))
    if result.scalar_one_or_none():
        return

    for index, category_data in enumerate(DEFAULT_CATEGORIES):
        db.add(Category(sort_order=index, **category_data))

    await db.commit()