from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models.models import Subscription, SubscriptionStatus, User
from app.core.config import settings


class SubscriptionService:

    @staticmethod
    async def get_active_subscription(db: AsyncSession, user_id: str) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        user_id: str,
        payment_provider: str,
        payment_ref: Optional[str] = None,
    ) -> Subscription:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)

        sub = Subscription(
            user_id=user_id,
            status=SubscriptionStatus.ACTIVE,
            plan="premium_monthly",
            price_fcfa=settings.PREMIUM_PRICE_FCFA,
            payment_provider=payment_provider,
            payment_ref=payment_ref,
            starts_at=now,
            expires_at=expires,
        )
        db.add(sub)

        # Activate premium on user
        await db.execute(
            update(User).where(User.id == user_id).values(is_premium=True)
        )

        await db.flush()
        return sub

    @staticmethod
    async def cancel_subscription(db: AsyncSession, subscription_id: str):
        await db.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=SubscriptionStatus.CANCELLED)
        )

    @staticmethod
    async def expire_subscriptions(db: AsyncSession):
        """Cron job: expire old subscriptions and downgrade users"""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at <= now,
            )
        )
        expired = result.scalars().all()

        for sub in expired:
            await db.execute(
                update(Subscription)
                .where(Subscription.id == sub.id)
                .values(status=SubscriptionStatus.EXPIRED)
            )
            await db.execute(
                update(User).where(User.id == sub.user_id).values(is_premium=False)
            )

        return len(expired)
