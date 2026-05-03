from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.ai_service import build_search_text, interpret_query
from app.services.commerce_service import CommerceService
from app.schemas.schemas import AISearchRequest, NearbySearchRequest

router = APIRouter()


def _format_result_hint(results: list[dict]) -> str:
    if not results:
        return ""

    names = [item.get("name") for item in results[:2] if item.get("name")]
    if not names:
        return ""
    if len(names) == 1:
        return f" Par exemple, vous pouvez regarder {names[0]}."
    return f" Par exemple, vous pouvez regarder {names[0]} ou {names[1]}."


def _build_ai_message(interpretation: dict, results: list[dict]) -> str:
    base_message = interpretation.get("ai_message", "Voici ce que j'ai trouvé près de vous")
    if not results:
        return (
            "Je n'ai rien trouvé d'assez pertinent autour de vous pour cette demande. "
            "Essayez un quartier, une catégorie ou un besoin plus précis."
        )

    first_distance = results[0].get("distance_km")
    distance_hint = ""
    if isinstance(first_distance, (int, float)):
        distance_hint = f" La meilleure option repérée est à environ {first_distance:.1f} km."

    return (
        f"{base_message} J'ai trouvé {len(results)} option(s) qui valent le détour."
        f"{distance_hint}{_format_result_hint(results)}"
    )


def _build_follow_up_suggestions(interpretation: dict, results: list) -> list[str]:
    category_slug = interpretation.get("category_slug")

    if category_slug == "restaurants":
        return [
            "montre-moi les plus proches",
            "je veux ceux qui sont ouverts maintenant",
            "je cherche les moins chers",
        ]
    if category_slug == "pharmacies":
        return [
            "je veux une pharmacie de garde",
            "montre-moi les plus proches",
            "je cherche quelque chose d'ouvert maintenant",
        ]
    if category_slug == "gaz-energie":
        return [
            "je veux un point de gaz vraiment proche",
            "montre-moi les options ouvertes",
            "je cherche un dépôt facile d'accès",
        ]
    if results:
        return [
            "montre-moi les plus proches",
            "je veux une meilleure option",
            "je cherche quelque chose d'ouvert maintenant",
        ]
    return [
        "essaie avec un quartier précis",
        "cherche une catégorie proche",
        "montre-moi ce qui est ouvert maintenant",
    ]


@router.post("/search")
async def ai_search(
    data: AISearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Natural language AI-powered search.
    
    Examples:
    - "je cherche un maquis pas cher"
    - "où trouver du gaz"
    - "mécanicien ouvert maintenant"
    - "coiffeur femme dans le quartier"
    """
    # Interpret the query
    interpretation = await interpret_query(
        data.query,
        data.language,
        conversation_history=data.conversation_history,
    )

    results = []
    if data.latitude and data.longitude:
        search_keywords = interpretation.get("search_keywords", [])
        query_text = build_search_text(search_keywords)
        category_slug = interpretation.get("category_slug")
        radius_km = 8.0 if category_slug in {"restaurants", "pharmacies", "gaz-energie"} else 5.0

        # Search with AI-interpreted parameters
        req = NearbySearchRequest(
            latitude=data.latitude,
            longitude=data.longitude,
            radius_km=radius_km,
            category_slug=category_slug,
            query=query_text,
            page=1,
            limit=10,
        )
        results, _ = await CommerceService.search_nearby(
            db, req, is_premium=current_user.is_premium or current_user.is_admin
        )

        if not results and category_slug:
            relaxed_req = NearbySearchRequest(
                latitude=data.latitude,
                longitude=data.longitude,
                radius_km=max(radius_km, 10.0),
                category_slug=None,
                query=query_text,
                page=1,
                limit=10,
            )
            results, _ = await CommerceService.search_nearby(
                db,
                relaxed_req,
                is_premium=current_user.is_premium or current_user.is_admin,
            )

    ai_message = _build_ai_message(interpretation, results)

    return {
        "query": data.query,
        "interpretation": interpretation.get("interpretation", ""),
        "category_suggestion": interpretation.get("category_slug"),
        "search_keywords": interpretation.get("search_keywords", []),
        "ai_message": ai_message,
        "follow_up_suggestions": _build_follow_up_suggestions(interpretation, results),
        "results": results,
        "result_count": len(results),
    }


@router.post("/suggestions")
async def get_suggestions(
    latitude: float,
    longitude: float,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get personalized AI recommendations based on location and time"""
    from datetime import datetime

    hour = datetime.now().hour
    suggestions = []

    if 6 <= hour <= 10:
        suggestions = [
            {"query": "pain chaud près de moi", "icon": "🥖", "label": "Boulangeries ouvertes"},
            {"query": "café du matin", "icon": "☕", "label": "Café & petit déjeuner"},
        ]
    elif 11 <= hour <= 14:
        suggestions = [
            {"query": "restaurant déjeuner", "icon": "🍽️", "label": "Déjeuner à proximité"},
            {"query": "maquis pas cher", "icon": "🍲", "label": "Maquis abordables"},
        ]
    elif 15 <= hour <= 18:
        suggestions = [
            {"query": "snack après-midi", "icon": "🥤", "label": "Snacks & boissons"},
            {"query": "supermarché", "icon": "🛒", "label": "Courses du soir"},
        ]
    else:
        suggestions = [
            {"query": "pharmacie de garde", "icon": "💊", "label": "Pharmacie de garde"},
            {"query": "maquis ouvert soir", "icon": "🌙", "label": "Restaurants ouverts"},
        ]

    return {
        "suggestions": suggestions,
        "time_context": f"{hour}h",
        "message": "Suggestions pour vous en ce moment 🎯",
    }
