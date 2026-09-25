"""HTTP contract tests using an isolated in-memory database, never project data."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.models.models import Category, Commerce, CommerceStatus, Merchant, User
from app.api.v1.endpoints import search, commerces, ai_assistant


@pytest.fixture
def client():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(User(id='owner', phone='+22670000001', full_name='Test'))
            db.add(Category(id='category', name='Boutique', slug='boutiques'))
            await db.flush()
            db.add(Merchant(id='merchant', user_id='owner', business_name='Boutique'))
            await db.flush()
            for status in [CommerceStatus.ACTIVE, CommerceStatus.PENDING, CommerceStatus.SUSPENDED]:
                db.add(Commerce(
                    id=status.value, merchant_id='merchant', category_id='category',
                    name=f'Boutique {status.value}', slug=f'boutique-{status.value}',
                    latitude=12.3714, longitude=-1.5197, status=status,
                    phone='+22670000001', whatsapp='+22670000001',
                ))
            await db.commit()
        yield
        await engine.dispose()

    async def database():
        async with sessions() as db:
            yield db
            await db.commit()

    app = FastAPI(lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(search.router, prefix='/search')
    app.include_router(commerces.router, prefix='/commerces')
    app.include_router(ai_assistant.router, prefix='/ai')
    app.dependency_overrides[get_db] = database
    limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer expired-token'}])
def test_guest_search_has_contacts_and_only_active_shops(client, headers):
    response = client.get('/search/nearby', params={'latitude': 12.3714, 'longitude': -1.5197}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1
    assert data['results'][0]['id'] == 'active'
    assert data['results'][0]['phone'] == '+22670000001'
    assert data['results'][0]['whatsapp'] == '+22670000001'


def test_guest_can_read_shop_and_autocomplete(client):
    response = client.get('/commerces/active')
    assert response.status_code == 200
    assert response.json()['phone'] == '+22670000001'
    response = client.get('/search/autocomplete', params={'q': 'Boutique'})
    assert response.status_code == 200
    assert [item['id'] for item in response.json()] == ['active']
    for status in ['pending', 'suspended']:
        assert client.get(f'/commerces/{status}').status_code == 404


def test_guest_route_metrics_does_not_require_premium(client):
    with patch.object(search.GoogleRoutesService, 'compute_driving_metrics', AsyncMock(return_value=(1200, 4))):
        response = client.get('/search/route-metrics', params={
            'origin_lat': 12.37, 'origin_lng': -1.52,
            'destination_lat': 12.38, 'destination_lng': -1.51,
        })
    assert response.status_code == 200
    assert response.json()['distance_km'] == 1.2


def test_guest_ai_search(client):
    with patch.object(ai_assistant, 'interpret_query', AsyncMock(return_value={'search_keywords': ['Boutique']})):
        response = client.post('/ai/search', json={
            'query': 'Boutique', 'latitude': 12.3714, 'longitude': -1.5197,
        })
    assert response.status_code == 200
    assert response.json()['result_count'] == 1


def test_private_mutations_stay_protected(client):
    for method, path in [('POST', '/commerces/'), ('PUT', '/commerces/active'), ('POST', '/commerces/active/reviews')]:
        response = client.request(method, path, json={})
        assert response.status_code in (401, 403)


def test_public_call_tracking_only_accepts_active_shops(client):
    assert client.post('/commerces/active/click-call').status_code == 204
    assert client.post('/commerces/pending/click-call').status_code == 404


def test_public_search_is_rate_limited(client):
    for _ in range(60):
        assert client.get('/search/autocomplete', params={'q': 'Boutique'}).status_code == 200
    assert client.get('/search/autocomplete', params={'q': 'Boutique'}).status_code == 429
