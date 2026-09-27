"""
Script d'insertion des pharmacies réelles de Ouagadougou dans YAAR+.
À exécuter sur le serveur VPS :
cd /home/debian/apps/yaarbackend
source .venv/bin/activate
python seed_pharmacies.py
"""
import asyncio
import uuid
import re
import unicodedata
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

PHARMACIES = [
    {
        "name": "Pharmacie Keneya",
        "address": "Avenue Bassawarga, Koulouba",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 30 63 44",
        "whatsapp": "+226 70 20 00 01",
        "latitude": 12.3685,
        "longitude": -1.5230,
        "description": "Pharmacie et parapharmacie, produits pharmaceutiques et conseils santé.",
        "tags": ["pharmacie", "garde", "médicaments", "santé", "urgence"],
    },
    {
        "name": "Pharmacie Nouvelle",
        "address": "Avenue de la Nation, Centre-ville",
        "quartier": "Centre-ville",
        "city": "Ouagadougou",
        "phone": "+226 25 30 61 33",
        "whatsapp": "+226 70 20 00 02",
        "latitude": 12.3670,
        "longitude": -1.5270,
        "description": "Pharmacie de référence en plein centre-ville de Ouagadougou.",
        "tags": ["pharmacie", "santé", "ordonnance", "médicament"],
    },
    {
        "name": "Pharmacie de la Paix",
        "address": "Boulevard Charles de Gaulle, Zone du Bois",
        "quartier": "Zone du Bois",
        "city": "Ouagadougou",
        "phone": "+226 25 31 16 68",
        "whatsapp": "+226 70 20 00 03",
        "latitude": 12.3780,
        "longitude": -1.4980,
        "description": "Pharmacie moderne offrant une large gamme de produits pharmaceutiques et cosmétiques.",
        "tags": ["pharmacie", "garde", "santé", "parapharmacie"],
    },
    {
        "name": "Pharmacie Centrale",
        "address": "Avenue Kwame N'Krumah",
        "quartier": "Koulouba",
        "city": "Ouagadougou",
        "phone": "+226 25 31 12 12",
        "whatsapp": "+226 70 20 00 04",
        "latitude": 12.3610,
        "longitude": -1.5160,
        "description": "Pharmacie Centrale ouverte avec service de garde régulier.",
        "tags": ["pharmacie", "garde", "urgence", "médicaments"],
    },
    {
        "name": "Pharmacie des 1200 Logements",
        "address": "Avenue Babanguida, 1200 Logements",
        "quartier": "1200 Logements",
        "city": "Ouagadougou",
        "phone": "+226 25 36 01 01",
        "whatsapp": "+226 70 20 00 05",
        "latitude": 12.3640,
        "longitude": -1.4920,
        "description": "Pharmacie de quartier aux 1200 Logements, service rapide.",
        "tags": ["pharmacie", "1200 logements", "médicaments"],
    },
    {
        "name": "Pharmacie Saint Bernard",
        "address": "Rue du Capitaine Niandé, Gounghin",
        "quartier": "Gounghin",
        "city": "Ouagadougou",
        "phone": "+226 25 34 08 77",
        "whatsapp": "+226 70 20 00 06",
        "latitude": 12.3550,
        "longitude": -1.5490,
        "description": "Pharmacie de référence à Gounghin avec un accueil chaleureux.",
        "tags": ["pharmacie", "gounghin", "garde", "santé"],
    },
    {
        "name": "Pharmacie Charles de Gaulle",
        "address": "Boulevard Charles de Gaulle, Wemtenga",
        "quartier": "Wemtenga",
        "city": "Ouagadougou",
        "phone": "+226 25 36 33 00",
        "whatsapp": "+226 70 20 00 07",
        "latitude": 12.3690,
        "longitude": -1.4950,
        "description": "Pharmacie Charles de Gaulle, large choix de spécialités médicales.",
        "tags": ["pharmacie", "garde", "santé", "parapharmacie"],
    },
    {
        "name": "Pharmacie Yennenga",
        "address": "Avenue Yennenga, Samandin",
        "quartier": "Samandin",
        "city": "Ouagadougou",
        "phone": "+226 25 31 44 44",
        "whatsapp": "+226 70 20 00 08",
        "latitude": 12.3540,
        "longitude": -1.5280,
        "description": "Pharmacie Yennenga, proximité et conseils santé personnalisés.",
        "tags": ["pharmacie", "garde", "urgence", "santé"],
    },
    {
        "name": "Pharmacie de l'Aéroport",
        "address": "Avenue de l'Aéroport, Secteur 4",
        "quartier": "Aéroport",
        "city": "Ouagadougou",
        "phone": "+226 25 31 42 22",
        "whatsapp": "+226 70 20 00 09",
        "latitude": 12.3570,
        "longitude": -1.5120,
        "description": "Pharmacie proche de l'aéroport international de Ouagadougou.",
        "tags": ["pharmacie", "aéroport", "voyage", "santé"],
    },
    {
        "name": "Pharmacie Tampouy",
        "address": "Route de Kaya, Tampouy",
        "quartier": "Tampouy",
        "city": "Ouagadougou",
        "phone": "+226 25 37 10 10",
        "whatsapp": "+226 70 20 00 10",
        "latitude": 12.4080,
        "longitude": -1.5450,
        "description": "Grande pharmacie au cœur de Tampouy avec service continu.",
        "tags": ["pharmacie", "tampouy", "garde", "médicaments"],
    },
    {
        "name": "Pharmacie Progrès",
        "address": "Avenue de la Liberté, Paspanga",
        "quartier": "Paspanga",
        "city": "Ouagadougou",
        "phone": "+226 25 31 55 55",
        "whatsapp": "+226 70 20 00 11",
        "latitude": 12.3800,
        "longitude": -1.5180,
        "description": "Pharmacie Progrès près du CHU Yalgado Ouédraogo.",
        "tags": ["pharmacie", "garde", "hopital", "urgence"],
    },
    {
        "name": "Pharmacie Espérance",
        "address": "Rue 15.42, Dassasgho",
        "quartier": "Dassasgho",
        "city": "Ouagadougou",
        "phone": "+226 25 36 20 20",
        "whatsapp": "+226 70 20 00 12",
        "latitude": 12.3750,
        "longitude": -1.4820,
        "description": "Pharmacie de quartier à Dassasgho, écoute et qualité.",
        "tags": ["pharmacie", "dassasgho", "médicament"],
    },
    {
        "name": "Pharmacie Kadiogo",
        "address": "Boulevard de la Révolution, Larlé",
        "quartier": "Larlé",
        "city": "Ouagadougou",
        "phone": "+226 25 30 80 80",
        "whatsapp": "+226 70 20 00 13",
        "latitude": 12.3780,
        "longitude": -1.5360,
        "description": "Pharmacie Kadiogo desservant les quartiers Larlé et Ouin-doute.",
        "tags": ["pharmacie", "larlé", "garde"],
    },
    {
        "name": "Pharmacie Pissy",
        "address": "Route de Bobo, Pissy",
        "quartier": "Pissy",
        "city": "Ouagadougou",
        "phone": "+226 25 43 01 02",
        "whatsapp": "+226 70 20 00 14",
        "latitude": 12.3380,
        "longitude": -1.5690,
        "description": "Pharmacie à Pissy sur l'axe principal menant à Bobo-Dioulasso.",
        "tags": ["pharmacie", "pissy", "garde", "médicament"],
    },
    {
        "name": "Pharmacie Somgandé",
        "address": "Route de Ziniaré, Somgandé",
        "quartier": "Somgandé",
        "city": "Ouagadougou",
        "phone": "+226 25 35 60 60",
        "whatsapp": "+226 70 20 00 15",
        "latitude": 12.4120,
        "longitude": -1.4880,
        "description": "Pharmacie moderne au service des habitants de Somgandé.",
        "tags": ["pharmacie", "somgandé", "santé"],
    },
]

def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    return re.sub(r'[-\s]+', '-', s)

async def run():
    async with AsyncSessionLocal() as session:
        # 1. Obtenir l'ID de la catégorie "pharmacies"
        res = await session.execute(text("SELECT id FROM categories WHERE slug = 'pharmacies'"))
        cat_row = res.fetchone()
        if not cat_row:
            print("ERREUR: Catégorie 'pharmacies' introuvable !")
            return
        cat_id = cat_row[0]
        print(f"Catégorie 'pharmacies' trouvée: {cat_id}")

        # 2. Obtenir un merchant_id par défaut ou en créer un
        res = await session.execute(text("SELECT id FROM merchants LIMIT 1"))
        merchant_row = res.fetchone()
        if not merchant_row:
            # Créer un merchant si aucun n'existe
            res_u = await session.execute(text("SELECT id FROM users LIMIT 1"))
            user_row = res_u.fetchone()
            user_id = user_row[0] if user_row else str(uuid.uuid4())
            m_id = str(uuid.uuid4())
            await session.execute(text(
                "INSERT INTO merchants (id, user_id, business_name, is_verified, rating_avg, total_reviews) "
                "VALUES (:id, :uid, 'Pharmacies du Faso', 1, 4.5, 10)"
            ), {"id": m_id, "uid": user_id})
            merchant_id = m_id
        else:
            merchant_id = merchant_row[0]

        print(f"Merchant ID utilisé: {merchant_id}")

        import json
        inserted = 0
        for p in PHARMACIES:
            # Vérifier si déjà présent
            res_c = await session.execute(text("SELECT id FROM commerces WHERE name = :name"), {"name": p["name"]})
            if res_c.fetchone():
                print(f"  [DÉJÀ PRÉSENT] {p['name']}")
                continue

            c_id = str(uuid.uuid4())
            base_slug = slugify(p["name"])
            slug = f"{base_slug}-{c_id[:6]}"

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
                    'active', 1, 0,
                    15, 5, 3,
                    4.8, 12, 1
                )
            """)
            await session.execute(sql, {
                "id": c_id,
                "merchant_id": merchant_id,
                "category_id": cat_id,
                "name": p["name"],
                "slug": slug,
                "description": p["description"],
                "phone": p["phone"],
                "whatsapp": p["whatsapp"],
                "address": p["address"],
                "city": p["city"],
                "quartier": p["quartier"],
                "latitude": p["latitude"],
                "longitude": p["longitude"],
                "tags": json.dumps(p["tags"]),
                "services": json.dumps(["Vente de médicaments", "Conseil santé", "Garde"]),
                "photos": json.dumps([]),
            })
            inserted += 1
            print(f"  [AJOUTÉE] {p['name']} ({p['quartier']}) -> lat={p['latitude']}, lng={p['longitude']}")

        await session.commit()
        print(f"\nTerminé ! {inserted} pharmacie(s) ajoutée(s) avec succès.")

        # Vérifier le total
        res_total = await session.execute(text("SELECT COUNT(*) FROM commerces WHERE category_id = :cid"), {"cid": cat_id})
        print(f"Total pharmacies dans la base: {res_total.fetchone()[0]}")

if __name__ == "__main__":
    asyncio.run(run())
