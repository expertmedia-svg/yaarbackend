from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, commerces, categories,
    search, subscriptions, events, ai_assistant,
    notifications, admin, upload, surveyor,
    store_photos, categories_enhanced, advertising, admin_roles
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(commerces.router, prefix="/commerces", tags=["Commerces"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(search.router, prefix="/search", tags=["Search & Geo"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Premium"])
api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(ai_assistant.router, prefix="/ai", tags=["AI Assistant"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(surveyor.router)
api_router.include_router(store_photos.router)
api_router.include_router(categories_enhanced.router)
api_router.include_router(advertising.router)
api_router.include_router(admin_roles.router)
