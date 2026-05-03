import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, func, or_, select

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import AsyncSessionLocal
from app.models.models import Commerce, Merchant, User


FALLBACK_COORDINATES = [
    (12.3714, -1.5197),
    (11.1771, -4.2979),
    (12.2526, -2.3627),
    (13.5828, -2.4216),
]


def build_fallback_filter():
    rounded_lat = func.round(Commerce.latitude, 4)
    rounded_lng = func.round(Commerce.longitude, 4)
    return or_(
        *[
            (rounded_lat == lat) & (rounded_lng == lng)
            for lat, lng in FALLBACK_COORDINATES
        ]
    )


async def main(apply_changes: bool):
    async with AsyncSessionLocal() as session:
        query = (
            select(Commerce.id, Commerce.name, Commerce.city, Commerce.latitude, Commerce.longitude)
            .join(Merchant, Merchant.id == Commerce.merchant_id)
            .join(User, User.id == Merchant.user_id)
            .where(User.is_admin == True)
            .where(build_fallback_filter())
            .order_by(Commerce.created_at.desc())
        )
        rows = (await session.execute(query)).all()

        if not rows:
            print('Aucun commerce admin avec coordonnées de secours trouvé.')
            return

        print(f'{len(rows)} commerce(s) à nettoyer détecté(s).')
        for row in rows[:20]:
            print(f'- {row.name} | {row.city} | {row.latitude}, {row.longitude}')
        if len(rows) > 20:
            print(f'... et {len(rows) - 20} autre(s).')

        if not apply_changes:
            print('Mode simulation. Relance avec --apply pour supprimer ces commerces.')
            return

        ids = [row.id for row in rows]
        await session.execute(delete(Commerce).where(Commerce.id.in_(ids)))
        await session.commit()
        print(f'{len(ids)} commerce(s) supprimé(s).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Nettoie les commerces admin importés avec coordonnées de secours.')
    parser.add_argument('--apply', action='store_true', help='Supprime réellement les commerces détectés.')
    args = parser.parse_args()
    asyncio.run(main(args.apply))
