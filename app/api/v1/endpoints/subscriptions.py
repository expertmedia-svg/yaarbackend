from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.subscription_service import SubscriptionService
from app.schemas.schemas import SubscriptionCreate, SubscriptionResponse

router = APIRouter()


@router.get("/status")
async def get_subscription_status(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = await SubscriptionService.get_active_subscription(db, current_user.id)
    return {
        "is_premium": current_user.is_premium,
        "subscription": SubscriptionResponse.model_validate(sub) if sub else None,
        "price_fcfa": 100,
        "features": [
            "Appel direct aux commerçants",
            "WhatsApp direct",
            "Navigation GPS",
            "Géolocalisation précise",
            "Favoris illimités",
            "Suggestions IA",
            "Meilleurs vendeurs",
            "Commerces ouverts maintenant",
            "Historique de recherche",
            "Recommandations avancées",
        ],
    }


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Check no active subscription
    existing = await SubscriptionService.get_active_subscription(db, current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Vous avez déjà un abonnement actif")

    # In production: verify payment with provider before creating subscription
    # For Wave: verify payment_ref with Wave API
    # For Orange Money: verify with Orange API
    # For now, trust the payment_ref

    sub = await SubscriptionService.create_subscription(
        db,
        user_id=current_user.id,
        payment_provider=data.payment_provider,
        payment_ref=data.payment_ref,
    )

    return SubscriptionResponse.model_validate(sub)


@router.delete("/cancel")
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = await SubscriptionService.get_active_subscription(db, current_user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="Aucun abonnement actif")

    await SubscriptionService.cancel_subscription(db, sub.id)
    return {"message": "Abonnement annulé. Actif jusqu'au " + str(sub.expires_at.date())}
