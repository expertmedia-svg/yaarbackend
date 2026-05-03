"""
Seed script: populates categories, admin user, and sample data.
Run: python -m app.utils.seed
"""
import asyncio
from sqlalchemy import select

from app.core.default_categories import DEFAULT_CATEGORIES, ensure_default_categories
from app.core.database import AsyncSessionLocal
from app.models.models import Category, User, UserRole
from app.core.security import get_password_hash
import uuid


async def seed():
    async with AsyncSessionLocal() as db:
        await ensure_default_categories(db)

        for cat_data in DEFAULT_CATEGORIES:
            existing = await db.execute(select(Category).where(Category.slug == cat_data["slug"]))
            if existing.scalar_one_or_none():
                print(f"✅ Category: {cat_data['name']}")

        # Create admin user
        admin_phone = "+22600000000"
        existing_admin = await db.execute(
            select(User).where(User.phone == admin_phone)
        )
        admin_user = existing_admin.scalar_one_or_none()
        if not admin_user:
            admin = User(
                id=str(uuid.uuid4()),
                phone=admin_phone,
                full_name="Admin YAAR+",
                password_hash=get_password_hash("Admin@YAAR2024!"),
                role=UserRole.ADMIN,
                is_admin=True,
                is_active=True,
                is_phone_verified=True,
                referral_code="ADMIN001",
            )
            db.add(admin)
            print(f"✅ Admin user created: {admin_phone}")
        else:
            admin_user.full_name = "Admin YAAR+"
            admin_user.role = UserRole.ADMIN
            admin_user.is_admin = True
            admin_user.is_active = True
            admin_user.is_phone_verified = True
            if not admin_user.referral_code:
                admin_user.referral_code = "ADMIN001"
            print(f"✅ Existing user promoted to admin: {admin_phone}")

        await db.commit()
        print("\n🎉 Seed terminé avec succès!")


if __name__ == "__main__":
    asyncio.run(seed())
