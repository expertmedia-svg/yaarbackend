"""
Script d'insertion des commerces essentiels par catégorie à Ouagadougou
(Boulangeries, Gaz & Énergie, Garages, Coiffure & Beauté, Pressing, Épiceries)
À exécuter sur le serveur VPS :
cd /home/debian/apps/yaarbackend
source .venv/bin/activate
python seed_essential_categories.py
"""
import asyncio
import uuid
import re
import unicodedata
import json
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

COMMERCES_DATA = [
    # ── Boulangeries ─────────────────────────────────────────────────────────
    {
        "category_slug": "boulangeries",
        "name": "Boulangerie Wend-Konta",
        "address": "Avenue Babanguida, 1200 Logements",
        "quartier": "1200 Logements",
        "city": "Ouagadougou",
        "phone": "+226 25 36 12 34",
        "whatsapp": "+226 70 11 22 33",
        "latitude": 12.3660,
        "longitude": -1.4930,
        "description": "Pain chaud, viennoiseries, pâtisseries fines et sandwichs tous les jours.",
        "tags": ["boulangerie", "pain", "viennoiserie", "croissant", "patisserie", "petit-dejeuner"],
        "services": ["Vente sur place", "Emporter", "Commandes spéciales"],
    },
    {
        "category_slug": "boulangeries",
        "name": "Boulangerie Laafi",
        "address": "Boulevard Charles de Gaulle, Wemtenga",
        "quartier": "Wemtenga",
        "city": "Ouagadougou",
        "phone": "+226 25 36 45 67",
        "whatsapp": "+226 70 22 33 44",
        "latitude": 12.3700,
        "longitude": -1.4970,
        "description": "Boulangerie moderne reconnue pour ses baguettes fraîches et gâteaux d'anniversaire.",
        "tags": ["boulangerie", "pain", "gateau", "baguette", "snack"],
        "services": ["Pain chaud", "Gâteaux", "Boissons"],
    },
    {
        "category_slug": "boulangeries",
        "name": "Boulangerie Saint Honoré",
        "address": "Avenue Bassawarga, Centre-ville",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 31 78 90",
        "whatsapp": "+226 70 33 44 55",
        "latitude": 12.3650,
        "longitude": -1.5240,
        "description": "Artisan boulanger-pâtissier traditionnel au cœur de la ville.",
        "tags": ["boulangerie", "pain", "croissant", "patisserie"],
        "services": ["Vente sur place", "Pâtisserie personnalisée"],
    },
    {
        "category_slug": "boulangeries",
        "name": "Boulangerie de la Paix Gounghin",
        "address": "Rue du Capitaine Niandé, Gounghin",
        "quartier": "Gounghin",
        "city": "Ouagadougou",
        "phone": "+226 25 34 23 12",
        "whatsapp": "+226 70 44 55 66",
        "latitude": 12.3570,
        "longitude": -1.5470,
        "description": "Fournée continue matin, midi et soir pour du pain toujours croustillant.",
        "tags": ["boulangerie", "pain chaud", "gounghin"],
        "services": ["Pain chaud H24", "Sandwich"],
    },

    # ── Gaz & Énergie ────────────────────────────────────────────────────────
    {
        "category_slug": "gaz-energie",
        "name": "Dépôt Gaz TotalEnergies Koulouba",
        "address": "Avenue Bassawarga, Koulouba",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 30 11 22",
        "whatsapp": "+226 76 01 02 03",
        "latitude": 12.3675,
        "longitude": -1.5225,
        "description": "Bouteilles de gaz B6 et B12 disponibles, accessoires et recharge express.",
        "tags": ["gaz", "recharge", "total", "energie", "bouteille gaz", "b6", "b12"],
        "services": ["Vente bouteilles", "Recharge", "Livraison à domicile"],
    },
    {
        "category_slug": "gaz-energie",
        "name": "Sodigaz Express Wemtenga",
        "address": "Boulevard Charles de Gaulle, Wemtenga",
        "quartier": "Wemtenga",
        "city": "Ouagadougou",
        "phone": "+226 25 36 88 99",
        "whatsapp": "+226 76 11 22 33",
        "latitude": 12.3710,
        "longitude": -1.4940,
        "description": "Point agréé Sodigaz, approvisionnement régulier sans rupture.",
        "tags": ["gaz", "sodigaz", "bouteille", "cuisine", "detendeur"],
        "services": ["Recharge gaz", "Accessoires gaz", "Livraison moto"],
    },
    {
        "category_slug": "gaz-energie",
        "name": "Dépôt Gaz Oryx Gounghin",
        "address": "Route de Bobo, Gounghin",
        "quartier": "Gounghin",
        "city": "Ouagadougou",
        "phone": "+226 25 34 55 66",
        "whatsapp": "+226 76 22 33 44",
        "latitude": 12.3530,
        "longitude": -1.5510,
        "description": "Recharge rapide gaz Oryx et Total, brûleurs, tuyaux et raccords sécurisés.",
        "tags": ["gaz", "oryx", "gounghin", "energie"],
        "services": ["Vente de gaz", "Dépannage raccords"],
    },
    {
        "category_slug": "gaz-energie",
        "name": "Point Gaz & Énergie Tampouy",
        "address": "Route de Kaya, Tampouy",
        "quartier": "Tampouy",
        "city": "Ouagadougou",
        "phone": "+226 25 37 44 55",
        "whatsapp": "+226 76 33 44 55",
        "latitude": 12.4060,
        "longitude": -1.5420,
        "description": "Distribution de gaz domestique et panneaux solaires de qualité.",
        "tags": ["gaz", "tampouy", "solaire", "batterie", "energie"],
        "services": ["Vente de gaz", "Équipement solaire"],
    },

    # ── Garages & Mécanique ──────────────────────────────────────────────────
    {
        "category_slug": "garages-mecaniques",
        "name": "Garage Auto Expert Gounghin",
        "address": "Avenue Kadiogo, Gounghin",
        "quartier": "Gounghin",
        "city": "Ouagadougou",
        "phone": "+226 25 34 11 00",
        "whatsapp": "+226 78 11 22 33",
        "latitude": 12.3580,
        "longitude": -1.5480,
        "description": "Diagnostic électronique, mécanique générale, vidange, freinage et climatisation auto.",
        "tags": ["garage", "mecanique", "auto", "reparation", "vidange", "freins", "climatisation"],
        "services": ["Diagnostic valise", "Entretien complet", "Dépannage remorquage"],
    },
    {
        "category_slug": "garages-mecaniques",
        "name": "Garage Moderne 1200 Logements",
        "address": "Avenue Babanguida, 1200 Logements",
        "quartier": "1200 Logements",
        "city": "Ouagadougou",
        "phone": "+226 25 36 22 11",
        "whatsapp": "+226 78 22 33 44",
        "latitude": 12.3630,
        "longitude": -1.4910,
        "description": "Spécialiste toutes marques européennes et japonaises, pièces d'origine.",
        "tags": ["garage", "mecanicien", "voiture", "pneus", "parallélisme"],
        "services": ["Révision", "Pneumatique", "Électricité auto"],
    },
    {
        "category_slug": "garages-mecaniques",
        "name": "Atelier Moto & Scooter Larlé",
        "address": "Boulevard de la Révolution, Larlé",
        "quartier": "Larlé",
        "city": "Ouagadougou",
        "phone": "+226 70 88 99 00",
        "whatsapp": "+226 78 33 44 55",
        "latitude": 12.3790,
        "longitude": -1.5350,
        "description": "Réparation rapide deux-roues, vidange moto, pièces détachées et pneumatiques.",
        "tags": ["garage", "moto", "scooter", "mecanique moto", "reparation"],
        "services": ["Entretien moto", "Changement pneu moto"],
    },

    # ── Coiffure & Beauté ────────────────────────────────────────────────────
    {
        "category_slug": "coiffure-beaute",
        "name": "Salon Élite Coiffure Homme & Dame",
        "address": "Avenue Kwame N'Krumah, Centre-ville",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 31 33 44",
        "whatsapp": "+226 72 11 22 33",
        "latitude": 12.3620,
        "longitude": -1.5170,
        "description": "Coupes modernes, tresses africaines, soins du visage, manucure et pédicure.",
        "tags": ["coiffure", "beaute", "salon", "tresses", "barbier", "soins", "cheveux"],
        "services": ["Coupe homme", "Coiffure dame", "Soins esthétiques"],
    },
    {
        "category_slug": "coiffure-beaute",
        "name": "Beauty Faso & Spa Zone du Bois",
        "address": "Rue 13.02, Zone du Bois",
        "quartier": "Zone du Bois",
        "city": "Ouagadougou",
        "phone": "+226 25 36 77 88",
        "whatsapp": "+226 72 22 33 44",
        "latitude": 12.3770,
        "longitude": -1.4990,
        "description": "Institut de beauté de standing, massage relaxant, maquillage professionnel.",
        "tags": ["beaute", "spa", "coiffure", "massage", "onglerie", "maquillage"],
        "services": ["Massage", "Onglerie", "Maquillage mariée"],
    },
    {
        "category_slug": "coiffure-beaute",
        "name": "Barbier Le Gentleman Wemtenga",
        "address": "Boulevard Charles de Gaulle, Wemtenga",
        "quartier": "Wemtenga",
        "city": "Ouagadougou",
        "phone": "+226 70 55 66 77",
        "whatsapp": "+226 72 33 44 55",
        "latitude": 12.3680,
        "longitude": -1.4960,
        "description": "Barbier traditionnel et moderne, dégradé américain, serviette chaude et soins barbe.",
        "tags": ["coiffure", "barbier", "barbe", "gentleman", "coupe homme"],
        "services": ["Taille de barbe", "Coupe stylée", "Soin visage homme"],
    },

    # ── Épiceries & Alimentation ─────────────────────────────────────────────
    {
        "category_slug": "epiceries-boutiques",
        "name": "Superette Le Bon Choix",
        "address": "Avenue Babanguida, 1200 Logements",
        "quartier": "1200 Logements",
        "city": "Ouagadougou",
        "phone": "+226 25 36 99 00",
        "whatsapp": "+226 74 11 22 33",
        "latitude": 12.3655,
        "longitude": -1.4935,
        "description": "Produits frais, épicerie générale, surgelés, boissons fraîches et hygiène.",
        "tags": ["epicerie", "superette", "alimentation", "boissons", "provisions"],
        "services": ["Libre-service", "Paiement mobile", "Livraison quartier"],
    },
    {
        "category_slug": "epiceries-boutiques",
        "name": "Alimentation Générale La Surface",
        "address": "Avenue de la Nation, Koulouba",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 30 88 11",
        "whatsapp": "+226 74 22 33 44",
        "latitude": 12.3675,
        "longitude": -1.5255,
        "description": "Grande alimentation bien achalandée en produits locaux et importés.",
        "tags": ["epicerie", "alimentation", "supermarche", "courses"],
        "services": ["Grand choix", "Fruits & légumes", "Produits laitiers"],
    },

    # ── Pressing & Laverie ───────────────────────────────────────────────────
    {
        "category_slug": "pressing-laverie",
        "name": "Pressing Éclair Ouaga",
        "address": "Boulevard Charles de Gaulle, Wemtenga",
        "quartier": "Wemtenga",
        "city": "Ouagadougou",
        "phone": "+226 25 36 00 22",
        "whatsapp": "+226 75 11 22 33",
        "latitude": 12.3695,
        "longitude": -1.4955,
        "description": "Nettoyage à sec, repassage express en 24h, traitement linge délicat et costumes.",
        "tags": ["pressing", "laverie", "repassage", "nettoyage", "costume"],
        "services": ["Nettoyage à sec", "Repassage express", "Lavage couette"],
    },
    {
        "category_slug": "pressing-laverie",
        "name": "Laverie Moderne Koulouba",
        "address": "Avenue Bassawarga, Koulouba",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 30 44 55",
        "whatsapp": "+226 75 22 33 44",
        "latitude": 12.3665,
        "longitude": -1.5235,
        "description": "Service de blanchisserie pour particuliers et professionnels avec ramassage possible.",
        "tags": ["pressing", "laverie", "blanchisserie", "linge"],
        "services": ["Lavage au kilo", "Service express", "Livraison domicile"],
    },
]

def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    return re.sub(r'[-\s]+', '-', s)

async def run():
    async with AsyncSessionLocal() as session:
        # Charger le dictionnaire slug -> category_id
        res_cats = await session.execute(text("SELECT slug, id FROM categories"))
        cat_map = {row[0]: row[1] for row in res_cats.fetchall()}
        print(f"Catégories en base: {list(cat_map.keys())}")

        # Merchant existant
        res_m = await session.execute(text("SELECT id FROM merchants LIMIT 1"))
        m_row = res_m.fetchone()
        merchant_id = m_row[0] if m_row else str(uuid.uuid4())

        inserted = 0
        for item in COMMERCES_DATA:
            cat_slug = item["category_slug"]
            cat_id = cat_map.get(cat_slug)
            if not cat_id:
                print(f"  [AVERTISSEMENT] Catégorie '{cat_slug}' introuvable, ignorée.")
                continue

            # Vérifier si déjà présent
            res_c = await session.execute(
                text("SELECT id FROM commerces WHERE name = :name"),
                {"name": item["name"]}
            )
            if res_c.fetchone():
                print(f"  [DÉJÀ PRÉSENT] {item['name']}")
                continue

            c_id = str(uuid.uuid4())
            slug = f"{slugify(item['name'])}-{c_id[:6]}"

            sql = text("""
                INSERT INTO commerces (
                    id, merchant_id, category_id, name, slug, description,
                    phone, whatsapp, address, city, quartier,
                    latitude, longitude, tags, services, photos,
                    status, is_featured, is_premium_listing,
                    view_count, click_call_count, click_whatsapp_count,
                    rating_avg, total_reviews, is_open_now
                ) VALUES (
                    :id, :merchant_id, :category_id, :name, :slug, :description,
                    :phone, :whatsapp, :address, :city, :quartier,
                    :latitude, :longitude, :tags, :services, :photos,
                    'ACTIVE', 1, 0,
                    20, 8, 5,
                    4.7, 10, 1
                )
            """)
            await session.execute(sql, {
                "id": c_id,
                "merchant_id": merchant_id,
                "category_id": cat_id,
                "name": item["name"],
                "slug": slug,
                "description": item["description"],
                "phone": item["phone"],
                "whatsapp": item["whatsapp"],
                "address": item["address"],
                "city": item["city"],
                "quartier": item["quartier"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "tags": json.dumps(item["tags"]),
                "services": json.dumps(item["services"]),
                "photos": json.dumps([]),
            })
            inserted += 1
            print(f"  [AJOUTÉ] {item['name']} ({cat_slug}) - {item['quartier']}")

        await session.commit()
        print(f"\nSuccès : {inserted} commerces insérés dans les catégories essentielles !")

        # Résumé par catégorie
        res_summary = await session.execute(text("""
            SELECT c.name, COUNT(co.id)
            FROM categories c
            LEFT JOIN commerces co ON co.category_id = c.id AND co.status = 'ACTIVE'
            GROUP BY c.name
            HAVING COUNT(co.id) > 0
            ORDER BY COUNT(co.id) DESC
        """))
        print("\n=== ÉTAT ACTUEL DES BOUTIQUES PAR CATÉGORIE ===")
        for r in res_summary.fetchall():
            print(f"  {r[0]}: {r[1]} commerces")

if __name__ == "__main__":
    asyncio.run(run())
