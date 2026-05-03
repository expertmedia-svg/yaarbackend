from openai import AsyncOpenAI
from typing import Optional, List
import json
from datetime import datetime

from app.core.config import settings

client: AsyncOpenAI | None = None
client_init_attempted = False


def get_openai_client() -> AsyncOpenAI | None:
    global client, client_init_attempted

    if client_init_attempted:
        return client

    client_init_attempted = True
    if not settings.OPENAI_API_KEY:
        return None

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as exc:
        print(f"OpenAI client unavailable: {exc}")
        client = None
    return client

CATEGORY_MAP = {
    "maquis": "restaurants",
    "restaurant": "restaurants",
    "resto": "restaurants",
    "manger": "restaurants",
    "nourriture": "restaurants",
    "repas": "restaurants",
    "grillade": "restaurants",
    "pizza": "restaurants",
    "brochette": "restaurants",
    "gaz": "gaz-energie",
    "butane": "gaz-energie",
    "carburant": "gaz-energie",
    "essence": "gaz-energie",
    "pain": "boulangeries",
    "boulangerie": "boulangeries",
    "patisserie": "boulangeries",
    "pâtisserie": "boulangeries",
    "pharmacie": "pharmacies",
    "medicament": "pharmacies",
    "médicament": "pharmacies",
    "ordonnance": "pharmacies",
    "coiffeur": "coiffure-beaute",
    "coiffeuse": "coiffure-beaute",
    "salon": "coiffure-beaute",
    "beaute": "coiffure-beaute",
    "beauté": "coiffure-beaute",
    "mécanicien": "garages-mecaniques",
    "garace": "garages-mecaniques",
    "garage": "garages-mecaniques",
    "voiture": "garages-mecaniques",
    "pressing": "pressing-laverie",
    "laverie": "pressing-laverie",
    "linge": "pressing-laverie",
    "artisan": "artisans",
    "menuisier": "artisans",
    "soudeur": "artisans",
    "fruits": "fruits-legumes",
    "légumes": "fruits-legumes",
    "legumes": "fruits-legumes",
    "marché": "marche-alimentaire",
    "marche": "marche-alimentaire",
    "boutique": "epiceries-boutiques",
    "épicerie": "epiceries-boutiques",
    "epicerie": "epiceries-boutiques",
    "supermarché": "epiceries-boutiques",
    "supermarche": "epiceries-boutiques",
    "kiosque": "kiosques",
    "condiment": "condiments-epices",
    "épice": "condiments-epices",
    "epice": "condiments-epices",
    "promo": "epiceries-boutiques",
}


VALID_CATEGORY_SLUGS = {
    "restaurants",
    "gaz-energie",
    "boulangeries",
    "pharmacies",
    "coiffure-beaute",
    "garages-mecaniques",
    "pressing-laverie",
    "artisans",
    "fruits-legumes",
    "marche-alimentaire",
    "epiceries-boutiques",
    "kiosques",
    "condiments-epices",
    "evenements-locaux",
    "autres-commerces",
}


GENERIC_SEARCH_KEYWORDS = {
    "pas cher",
    "moins cher",
    "cher",
    "ouvert",
    "ouverte",
    "ouvert maintenant",
    "ouverte maintenant",
    "proche",
    "proches",
    "plus proches",
    "maintenant",
    "autour de moi",
    "a proximite",
    "à proximité",
}


SYSTEM_PROMPT = """Tu es YAAR+, l'assistant intelligent de la super app africaine du marché de proximité.

Tu analyses les requêtes des utilisateurs en français (ou langues locales africaines) pour identifier :
1. Quelle catégorie de commerce ils cherchent
2. Les mots-clés de recherche pertinents
3. Un message de réponse sympathique et utile

Tu dois raisonner comme un assistant local utile et concret :
- privilégie les intentions réellement recherchables dans un marché de proximité
- conserve des mots-clés courts, utiles pour une recherche de commerces
- si la demande exprime une urgence (ex: pharmacie, gaz, panne, faim), reflète-le dans le message
- si la demande parle de budget, de proximité, d'ouverture ou de qualité, garde ces notions dans les mots-clés
- n'invente jamais de commerce précis

Réponds UNIQUEMENT en JSON avec ce format exact :
{
  "interpretation": "description courte de ce que l'utilisateur cherche",
  "category_slug": "slug de la catégorie (ou null si non déterminé)",
  "search_keywords": ["mot1", "mot2"],
  "ai_message": "Message sympa pour l'utilisateur en 1-2 phrases max"
}

Catégories disponibles (slugs) :
restaurants, gaz-energie, boulangeries, pharmacies, coiffure-beaute,
garages-mecaniques, pressing-laverie, artisans, fruits-legumes,
marche-alimentaire, epiceries-boutiques, kiosques, condiments-epices,
evenements-locaux, autres-commerces

Sois chaleureux, africain dans le ton, et utile."""


async def interpret_query(
    query: str,
    language: str = "fr",
    conversation_history: Optional[List[str]] = None,
) -> dict:
    """Use AI to interpret a natural language search query"""

    clean_query = " ".join(query.split()).strip()
    normalized_history = _normalize_history(conversation_history)
    if not clean_query:
        return _fallback_interpret(query)

    client = get_openai_client()
    if not client:
        # Fallback: simple keyword matching
        return _fallback_interpret(clean_query)

    try:
        current_hour = datetime.now().hour
        history_block = "\n".join(normalized_history) if normalized_history else "Aucun historique utile"
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Langue: {language}\n"
                        f"Heure locale approximative: {current_hour}h\n"
                        f"Historique récent: {history_block}\n"
                        f"Requête utilisateur: {clean_query}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return _sanitize_interpretation(
            json.loads(content),
            clean_query,
            conversation_history=normalized_history,
        )
    except Exception as e:
        print(f"AI error: {e}")
        return _fallback_interpret(clean_query, conversation_history=normalized_history)


def _sanitize_interpretation(
    payload: dict,
    original_query: str,
    conversation_history: Optional[List[str]] = None,
) -> dict:
    if not isinstance(payload, dict):
        return _fallback_interpret(original_query, conversation_history=conversation_history)

    category_slug = payload.get("category_slug")
    if category_slug not in VALID_CATEGORY_SLUGS:
        category_slug = _infer_category_from_keywords(original_query)

    search_keywords = payload.get("search_keywords") or []
    if not isinstance(search_keywords, list):
        search_keywords = []

    normalized_keywords: List[str] = []
    for keyword in search_keywords:
        if not isinstance(keyword, str):
            continue
        value = keyword.strip().lower()
        if (
            len(value) < 3
            or value in normalized_keywords
            or value in GENERIC_SEARCH_KEYWORDS
        ):
            continue
        normalized_keywords.append(value)

    if not normalized_keywords:
        normalized_keywords = _extract_keywords(original_query)

    interpretation = str(payload.get("interpretation") or "").strip()
    if not interpretation:
        interpretation = f"Recherche locale: {original_query}"

    ai_message = str(payload.get("ai_message") or "").strip()
    if not ai_message:
        ai_message = _fallback_interpret(
            original_query,
            conversation_history=conversation_history,
        )["ai_message"]

    return {
        "interpretation": interpretation,
        "category_slug": category_slug,
        "search_keywords": normalized_keywords[:6],
        "ai_message": ai_message,
    }


def _normalize_history(conversation_history: Optional[List[str]]) -> List[str]:
    if not conversation_history:
        return []

    normalized: List[str] = []
    for item in conversation_history[-6:]:
        if not isinstance(item, str):
            continue
        value = " ".join(item.split()).strip()
        if value:
            normalized.append(value[:240])
    return normalized


def _infer_category_from_keywords(query: str) -> Optional[str]:
    q_lower = query.lower()
    for keyword, slug in CATEGORY_MAP.items():
        if keyword in q_lower:
            return slug
    return None


def _extract_keywords(query: str) -> List[str]:
    common_words = {
        "je",
        "tu",
        "il",
        "elle",
        "nous",
        "vous",
        "ils",
        "elles",
        "cherche",
        "recherche",
        "veux",
        "veut",
        "trouver",
        "pres",
        "près",
        "moi",
        "dans",
        "avec",
        "pour",
        "une",
        "des",
        "les",
        "sur",
        "vers",
        "ici",
        "maintenant",
        "montre",
        "moi",
        "plus",
        "proche",
        "proches",
        "option",
        "options",
        "veux",
        "ceux",
        "celles",
    }
    keywords: List[str] = []
    for raw_word in query.lower().replace("'", " ").split():
        word = raw_word.strip(" ,.!?;:\"()[]{}")
        if len(word) < 3 or word in common_words or word in keywords:
            continue
        keywords.append(word)
    return keywords[:6]


def build_search_text(keywords: List[str]) -> Optional[str]:
    useful_keywords: List[str] = []
    for keyword in keywords:
        value = (keyword or "").strip().lower()
        if not value or value in GENERIC_SEARCH_KEYWORDS or value in useful_keywords:
            continue
        useful_keywords.append(value)

    if not useful_keywords:
        return None

    return " ".join(useful_keywords[:3])


def _fallback_interpret(
    query: str,
    conversation_history: Optional[List[str]] = None,
) -> dict:
    """Simple keyword matching when AI is unavailable"""
    category_slug = _infer_category_from_keywords(query)
    words = _extract_keywords(query)
    history_context = " ".join(conversation_history or []).lower()
    if not category_slug and history_context:
        category_slug = _infer_category_from_keywords(history_context)
    if len(words) < 2 and history_context:
        history_keywords = _extract_keywords(history_context)
        combined_words: List[str] = []
        for keyword in history_keywords + words:
            if keyword not in combined_words:
                combined_words.append(keyword)
        words = combined_words[:5]

    messages = {
        None: "Je recherche les commerces correspondants près de vous 📍",
        "restaurants": "Je cherche les meilleurs restaurants et maquis près de vous 🍽️",
        "pharmacies": "Je cherche les pharmacies disponibles près de vous 💊",
        "gaz-energie": "Je cherche les points de vente de gaz près de vous ⛽",
        "garages-mecaniques": "Je cherche les mécaniciens disponibles près de vous 🔧",
        "boulangeries": "Je cherche le bon pain chaud et les boulangeries proches de vous 🥖",
        "epiceries-boutiques": "Je cherche les boutiques et épiceries utiles autour de vous 🛒",
    }

    if conversation_history:
        base_message = messages.get(category_slug, messages[None])
        contextual_message = (
            "Je garde le fil de votre recherche pour affiner les résultats autour de vous. "
            f"{base_message}"
        )
    else:
        contextual_message = messages.get(category_slug, messages[None])

    return {
        "interpretation": f"Recherche: {query}",
        "category_slug": category_slug,
        "search_keywords": words[:5],
        "ai_message": contextual_message,
    }
