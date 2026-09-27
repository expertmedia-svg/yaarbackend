"""
Script de moissonnage automatique OpenStreetMap pour YAAR+ (Burkina Faso).
Récupère automatiquement toutes les boutiques, pharmacies, maquis, boulangeries,
stations/gaz, garages, etc. avec coordonnées GPS, téléphones, quartiers et adresses.

À exécuter sur le VPS :
cd /home/debian/apps/yaarbackend
source .venv/bin/activate
python osm_harvester.py
"""
import asyncio
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import uuid
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Zones à moissonner (Ouagadougou élargie, Bobo-Dioulasso, Koudougou)
ZONES = [
    {"name": "Ouagadougou", "city": "Ouagadougou", "bbox": (12.20, -1.68, 12.52, -1.35)},
    {"name": "Bobo-Dioulasso", "city": "Bobo-Dioulasso", "bbox": (11.10, -4.38, 11.26, -4.20)},
    {"name": "Koudougou", "city": "Koudougou", "bbox": (12.20, -2.42, 12.30, -2.32)},
]

CATEGORY_RULES = [
    ("pharmacies", lambda t: t.get("amenity") == "pharmacy" or "pharm" in (t.get("name") or "").lower() or t.get("shop") == "chemist"),
    ("boulangeries", lambda t: t.get("shop") in ("bakery", "pastry") or "boulang" in (t.get("name") or "").lower() or "patiss" in (t.get("name") or "").lower()),
    ("restaurants", lambda t: t.get("amenity") in ("restaurant", "fast_food", "cafe", "bar", "pub", "food_court") or "resto" in (t.get("name") or "").lower() or "maquis" in (t.get("name") or "").lower() or "grill" in (t.get("name") or "").lower()),
    ("gaz-energie", lambda t: t.get("amenity") == "fuel" or t.get("shop") == "gas" or "gaz" in (t.get("name") or "").lower() or "station" in (t.get("name") or "").lower() or "total" in (t.get("name") or "").lower() or "oryx" in (t.get("name") or "").lower() or "shell" in (t.get("name") or "").lower() or "sodigaz" in (t.get("name") or "").lower()),
    ("garages-mecaniques", lambda t: t.get("shop") in ("car_repair", "motorcycle_repair", "tyres") or t.get("craft") in ("car_repair", "motorcycle_repair") or "garage" in (t.get("name") or "").lower() or "mecanic" in (t.get("name") or "").lower() or "vulcanis" in (t.get("name") or "").lower()),
    ("coiffure-beaute", lambda t: t.get("shop") in ("hairdresser", "beauty", "cosmetics", "perfumery") or t.get("craft") in ("hairdresser",) or "coiff" in (t.get("name") or "").lower() or "beaut" in (t.get("name") or "").lower() or "salon" in (t.get("name") or "").lower() or "barbi" in (t.get("name") or "").lower() or "ongl" in (t.get("name") or "").lower()),
    ("epiceries-boutiques", lambda t: t.get("shop") in ("convenience", "supermarket", "general", "grocery", "deli") or "aliment" in (t.get("name") or "").lower() or "super" in (t.get("name") or "").lower() or "epicerie" in (t.get("name") or "").lower() or "libre-service" in (t.get("name") or "").lower()),
    ("marche-alimentaire", lambda t: t.get("amenity") == "marketplace" or t.get("shop") in ("butcher", "seafood", "greengrocer", "farm") or "marche" in (t.get("name") or "").lower() or "yaare" in (t.get("name") or "").lower() or "boucherie" in (t.get("name") or "").lower()),
    ("pressing-laverie", lambda t: t.get("shop") in ("laundry", "dry_cleaning") or "pressing" in (t.get("name") or "").lower() or "laverie" in (t.get("name") or "").lower() or "blanchiss" in (t.get("name") or "").lower()),
    ("kiosques", lambda t: t.get("shop") == "kiosk" or t.get("amenity") == "kiosk" or "kiosque" in (t.get("name") or "").lower() or "boutiquette" in (t.get("name") or "").lower()),
    ("artisans", lambda t: bool(t.get("craft")) or t.get("shop") in ("tailor", "shoemaker", "carpenter", "jewellery", "pottery", "blacksmith", "craft") or "coutur" in (t.get("name") or "").lower() or "menuiser" in (t.get("name") or "").lower() or "cordonn" in (t.get("name") or "").lower()),
    ("autres-commerces", lambda t: True),
]

def map_category(tags):
    for slug, rule in CATEGORY_RULES:
        if rule(tags):
            return slug
    return "autres-commerces"

def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    return re.sub(r'[-\s]+', '-', s)

def fetch_osm_elements(bbox):
    min_lat, min_lon, max_lat, max_lon = bbox
    query = f"""
    [out:json][timeout:60];
    (
      node["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["amenity"~"pharmacy|restaurant|fast_food|cafe|bar|fuel|bank|marketplace|kiosk"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["craft"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body;
    """
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    for mirror in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(mirror, data=data, headers={'User-Agent': 'YAARPlus/2.0 (osm-harvester)'})
            with urllib.request.urlopen(req, timeout=50) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                elements = result.get('elements', [])
                if elements:
                    return elements
        except Exception as e:
            print(f"  Mirror {mirror} indisponible ({e}), essai du miroir suivant...")
            continue
    return []

async def run():
    print("=" * 65)
    print("🌍 MOISSONNEUR AUTOMATIQUE OPENSTREETMAP POUR YAAR+ BURKINA")
    print("=" * 65)

    async with AsyncSessionLocal() as session:
        # Charger les catégories existantes
        res_cats = await session.execute(text("SELECT slug, id FROM categories"))
        cat_map = {row[0]: row[1] for row in res_cats.fetchall()}
        if not cat_map:
            print("ERREUR: Aucune catégorie trouvée dans la base !")
            return

        # Merchant par défaut
        res_m = await session.execute(text("SELECT id FROM merchants LIMIT 1"))
        m_row = res_m.fetchone()
        merchant_id = m_row[0] if m_row else str(uuid.uuid4())

        # Charger les noms existants pour dédoublonner
        res_existing = await session.execute(text("SELECT lower(name) FROM commerces"))
        existing_names = set(row[0] for row in res_existing.fetchall() if row[0])
        print(f"Commerces déjà en base : {len(existing_names)}")

        total_inserted = 0
        stats_by_cat = {}

        for zone in ZONES:
            print(f"\n📡 Récupération des données pour {zone['name']}...")
            elements = fetch_osm_elements(zone["bbox"])
            print(f"  {len(elements)} points trouvés dans {zone['name']}")

            inserted_zone = 0
            for el in elements:
                tags = el.get("tags", {})
                raw_name = tags.get("name")
                if not raw_name or len(raw_name.strip()) < 2:
                    continue

                name = raw_name.strip()
                norm_name = name.lower()
                if norm_name in existing_names:
                    continue

                existing_names.add(norm_name)

                cat_slug = map_category(tags)
                cat_id = cat_map.get(cat_slug) or cat_map.get("autres-commerces")

                # Récupérer coordonnées
                lat = el.get("lat")
                lon = el.get("lon")
                if not lat or not lon:
                    continue

                # Récupérer téléphone / contact
                phone = tags.get("phone") or tags.get("contact:phone") or tags.get("mobile")
                whatsapp = tags.get("contact:whatsapp") or tags.get("whatsapp") or phone

                # Adresse & Quartier
                street = tags.get("addr:street") or ""
                suburb = tags.get("addr:suburb") or tags.get("addr:district") or tags.get("neighbourhood") or ""
                housenumber = tags.get("addr:housenumber") or ""
                address_parts = [p for p in [housenumber, street] if p]
                address = " ".join(address_parts) if address_parts else f"Secteur {suburb}" if suburb else zone["name"]

                # Tags & services
                tag_list = [t for t in [tags.get("shop"), tags.get("amenity"), tags.get("craft"), cat_slug] if t]
                if tags.get("cuisine"):
                    tag_list.extend(tags.get("cuisine").split(";"))

                c_id = str(uuid.uuid4())
                slug = f"{slugify(name)[:80]}-{c_id[:6]}"

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
                        'ACTIVE', 0, 0,
                        5, 0, 0,
                        4.5, 3, 1
                    )
                """)

                desc_type = tags.get("shop") or tags.get("amenity") or tags.get("craft") or cat_slug
                desc = f"{name} - {desc_type.replace('_', ' ').capitalize()} à {zone['name']}."

                await session.execute(sql, {
                    "id": c_id,
                    "merchant_id": merchant_id,
                    "category_id": cat_id,
                    "name": name,
                    "slug": slug,
                    "description": desc,
                    "phone": phone,
                    "whatsapp": whatsapp,
                    "address": address,
                    "city": zone["city"],
                    "quartier": suburb or None,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "tags": json.dumps(tag_list[:8]),
                    "services": json.dumps([]),
                    "photos": json.dumps([]),
                })

                inserted_zone += 1
                total_inserted += 1
                stats_by_cat[cat_slug] = stats_by_cat.get(cat_slug, 0) + 1

            await session.commit()
            print(f"  ✅ {inserted_zone} nouveaux commerces ajoutés pour {zone['name']}")

        print("\n" + "=" * 65)
        print(f"🎉 MOISSONNAGE TERMINÉ : +{total_inserted} COMMERCES AJOUTÉS !")
        print("=" * 65)
        print("Répartition des nouveaux commerces :")
        for cat, cnt in sorted(stats_by_cat.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {cat}: +{cnt}")

        # Total global en base
        r_all = await session.execute(text("SELECT COUNT(*) FROM commerces WHERE status = 'ACTIVE'"))
        print(f"\n📊 TOTAL GLOBAL DES BOUTIQUES DANS YAAR+ : {r_all.fetchone()[0]}")

if __name__ == "__main__":
    asyncio.run(run())
