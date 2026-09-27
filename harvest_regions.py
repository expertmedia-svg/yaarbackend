"""
Script de moissonnage pour Bobo-Dioulasso, Koudougou et Ouahigouya.
Supporte les nodes ET les ways (bâtiments) avec 'out center'.
À exécuter sur le VPS :
cd /home/debian/apps/yaarbackend
source .venv/bin/activate
python harvest_regions.py
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

REGIONAL_ZONES = [
    {"name": "Bobo-Dioulasso", "city": "Bobo-Dioulasso", "bbox": (11.08, -4.42, 11.28, -4.18)},
    {"name": "Koudougou", "city": "Koudougou", "bbox": (12.18, -2.45, 12.35, -2.28)},
    {"name": "Ouahigouya", "city": "Ouahigouya", "bbox": (13.52, -2.46, 13.64, -2.36)},
]

CATEGORY_RULES = [
    ("pharmacies", lambda t: t.get("amenity") == "pharmacy" or "pharm" in (t.get("name") or "").lower() or t.get("shop") == "chemist"),
    ("boulangeries", lambda t: t.get("shop") in ("bakery", "pastry") or "boulang" in (t.get("name") or "").lower() or "patiss" in (t.get("name") or "").lower()),
    ("restaurants", lambda t: t.get("amenity") in ("restaurant", "fast_food", "cafe", "bar", "pub", "food_court") or "resto" in (t.get("name") or "").lower() or "maquis" in (t.get("name") or "").lower() or "grill" in (t.get("name") or "").lower()),
    ("gaz-energie", lambda t: t.get("amenity") == "fuel" or t.get("shop") == "gas" or "gaz" in (t.get("name") or "").lower() or "station" in (t.get("name") or "").lower() or "total" in (t.get("name") or "").lower() or "oryx" in (t.get("name") or "").lower() or "shell" in (t.get("name") or "").lower() or "sodigaz" in (t.get("name") or "").lower()),
    ("garages-mecaniques", lambda t: t.get("shop") in ("car_repair", "motorcycle_repair", "tyres") or t.get("craft") in ("car_repair", "motorcycle_repair") or "garage" in (t.get("name") or "").lower() or "mecanic" in (t.get("name") or "").lower()),
    ("coiffure-beaute", lambda t: t.get("shop") in ("hairdresser", "beauty", "cosmetics", "perfumery") or t.get("craft") in ("hairdresser",) or "coiff" in (t.get("name") or "").lower() or "beaut" in (t.get("name") or "").lower() or "salon" in (t.get("name") or "").lower()),
    ("epiceries-boutiques", lambda t: t.get("shop") in ("convenience", "supermarket", "general", "grocery", "deli") or "aliment" in (t.get("name") or "").lower() or "super" in (t.get("name") or "").lower() or "epicerie" in (t.get("name") or "").lower() or "coop" in (t.get("name") or "").lower()),
    ("marche-alimentaire", lambda t: t.get("amenity") == "marketplace" or t.get("shop") in ("butcher", "seafood", "greengrocer", "farm") or "marche" in (t.get("name") or "").lower() or "yaare" in (t.get("name") or "").lower()),
    ("pressing-laverie", lambda t: t.get("shop") in ("laundry", "dry_cleaning") or "pressing" in (t.get("name") or "").lower() or "laverie" in (t.get("name") or "").lower()),
    ("kiosques", lambda t: t.get("shop") == "kiosk" or t.get("amenity") == "kiosk" or "kiosque" in (t.get("name") or "").lower()),
    ("artisans", lambda t: bool(t.get("craft")) or t.get("shop") in ("tailor", "shoemaker", "carpenter", "jewellery", "pottery", "blacksmith", "craft") or "coutur" in (t.get("name") or "").lower() or "menuiser" in (t.get("name") or "").lower()),
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

def fetch_elements_for_bbox(bbox):
    min_lat, min_lon, max_lat, max_lon = bbox
    query = f"""
    [out:json][timeout:60];
    (
      node["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["amenity"~"pharmacy|restaurant|fast_food|cafe|bar|fuel|bank|marketplace|hospital|clinic|kiosk"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["craft"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"~"pharmacy|restaurant|fast_food|cafe|bar|fuel|bank|marketplace|hospital|clinic"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    for mirror in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(mirror, data=data, headers={'User-Agent': 'YAARPlus/2.0 (regional-harvester)'})
            with urllib.request.urlopen(req, timeout=55) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                elements = res.get('elements', [])
                if elements:
                    return elements
        except Exception as e:
            print(f"    Miroir {mirror} en attente ({e}), tentative miroir suivant...")
            continue
    return []

async def run():
    print("=" * 65)
    print("🌍 MOISSONNAGE POUR BOBO-DIOULASSO, KOUDOUGOU & OUAHIGOUYA")
    print("=" * 65)

    async with AsyncSessionLocal() as session:
        res_cats = await session.execute(text("SELECT slug, id FROM categories"))
        cat_map = {row[0]: row[1] for row in res_cats.fetchall()}

        res_m = await session.execute(text("SELECT id FROM merchants LIMIT 1"))
        m_row = res_m.fetchone()
        merchant_id = m_row[0] if m_row else str(uuid.uuid4())

        res_existing = await session.execute(text("SELECT lower(name) FROM commerces"))
        existing_names = set(row[0] for row in res_existing.fetchall() if row[0])
        print(f"Commerces existants en base : {len(existing_names)}")

        total_inserted = 0

        for zone in REGIONAL_ZONES:
            print(f"\n📡 Récupération des données pour {zone['name']}...")
            elements = fetch_elements_for_bbox(zone["bbox"])
            print(f"  -> {len(elements)} éléments trouvés sur la carte pour {zone['name']}")

            inserted_zone = 0
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name or len(name.strip()) < 2:
                    continue

                name = name.strip()
                norm_name = name.lower()
                if norm_name in existing_names:
                    continue

                existing_names.add(norm_name)

                # Extraire latitude et longitude (gère node direct ou way center)
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                if not lat or not lon:
                    continue

                cat_slug = map_category(tags)
                cat_id = cat_map.get(cat_slug) or cat_map.get("autres-commerces")

                phone = tags.get("phone") or tags.get("contact:phone") or tags.get("mobile")
                whatsapp = tags.get("contact:whatsapp") or tags.get("whatsapp") or phone

                street = tags.get("addr:street") or ""
                suburb = tags.get("addr:suburb") or tags.get("addr:district") or tags.get("neighbourhood") or ""
                housenumber = tags.get("addr:housenumber") or ""
                address_parts = [p for p in [housenumber, street] if p]
                address = " ".join(address_parts) if address_parts else f"Secteur {suburb}" if suburb else zone["name"]

                tag_list = [t for t in [tags.get("shop"), tags.get("amenity"), tags.get("craft"), cat_slug] if t]

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
                    "id": c_id, "merchant_id": merchant_id, "category_id": cat_id,
                    "name": name, "slug": slug, "description": desc,
                    "phone": phone, "whatsapp": whatsapp, "address": address,
                    "city": zone["city"], "quartier": suburb or None,
                    "latitude": float(lat), "longitude": float(lon),
                    "tags": json.dumps(tag_list[:8]), "services": json.dumps([]),
                    "photos": json.dumps([]),
                })
                inserted_zone += 1
                total_inserted += 1

            await session.commit()
            print(f"  ✅ {inserted_zone} boutiques ajoutées pour {zone['name']} !")

        print("\n" + "=" * 65)
        print(f"🎉 SUCCÈS : +{total_inserted} NOUVEAUX COMMERCES AJOUTÉS !")
        print("=" * 65)

        # Rapport par ville
        res_cities = await session.execute(text("""
            SELECT city, COUNT(*)
            FROM commerces
            WHERE status = 'ACTIVE'
            GROUP BY city
            ORDER BY COUNT(*) DESC
        """))
        print("\n📍 RÉPARTITION DES BOUTIQUES PAR VILLE :")
        for r in res_cities.fetchall():
            print(f"  - {r[0]}: {r[1]} commerces")

        r_total = await session.execute(text("SELECT COUNT(*) FROM commerces WHERE status = 'ACTIVE'"))
        print(f"\n📊 TOTAL GLOBAL BURKINA FASO : {r_total.fetchone()[0]} boutiques actives !")

if __name__ == "__main__":
    asyncio.run(run())
