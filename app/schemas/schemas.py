from pydantic import Field

from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# ── Auth Schemas ───────────────────────────────────────────────────────────────

class PhoneRegisterRequest(BaseModel):
    phone: str
    full_name: str
    referral_code: Optional[str] = None
    pin: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        # Accept African phone formats
        v = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{8,15}$", v):
            raise ValueError("Numéro de téléphone invalide")
        return v

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value):
        if value is None or value == "":
            return None
        if not re.match(r"^[0-9]{4,6}$", value):
            raise ValueError("Le code PIN doit contenir 4 à 6 chiffres")
        return value


class OTPVerifyRequest(BaseModel):
    phone: str
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value):
        if not re.match(r"^[0-9]{4,6}$", value):
            raise ValueError("Le code PIN doit contenir 4 à 6 chiffres")
        return value


class LoginRequest(BaseModel):
    phone: str
    pin: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        v = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{8,15}$", v):
            raise ValueError("Numéro de téléphone invalide")
        return v

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value):
        if not re.match(r"^[0-9]{4,6}$", value):
            raise ValueError("Le code PIN doit contenir 4 à 6 chiffres")
        return value


class PinSetupRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value):
        if not re.match(r"^[0-9]{4,6}$", value):
            raise ValueError("Le code PIN doit contenir 4 à 6 chiffres")
        return value


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User Schemas ───────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    phone: str
    email: Optional[str]
    full_name: str
    avatar_url: Optional[str]
    role: str
    is_premium: bool
    is_phone_verified: bool
    referral_code: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    fcm_token: Optional[str] = None


class UserLocationUpdate(BaseModel):
    latitude: float
    longitude: float


# ── Category Schemas ───────────────────────────────────────────────────────────

class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon: Optional[str]
    color: Optional[str]
    description: Optional[str]
    parent_id: Optional[str]
    sort_order: int

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str
    slug: str
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: int = 0


# ── Commerce Schemas ───────────────────────────────────────────────────────────

class OpeningHours(BaseModel):
    mon: Optional[List[str]] = None
    tue: Optional[List[str]] = None
    wed: Optional[List[str]] = None
    thu: Optional[List[str]] = None
    fri: Optional[List[str]] = None
    sat: Optional[List[str]] = None
    sun: Optional[List[str]] = None


class CommerceCreate(BaseModel):
    name: str
    category_id: str
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    city: str
    quartier: Optional[str] = None
    latitude: float
    longitude: float
    opening_hours: Optional[OpeningHours] = None
    tags: List[str] = []
    services: List[str] = []


class CommerceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    opening_hours: Optional[OpeningHours] = None
    tags: Optional[List[str]] = None
    services: Optional[List[str]] = None


class AdminCommerceCreate(BaseModel):
    name: str
    category_id: str
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    city: str
    quartier: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[OpeningHours] = None
    tags: List[str] = []
    services: List[str] = []
    auto_activate: bool = True


class AdminCommerceImportItem(BaseModel):
    name: str
    category_id: str
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    city: str
    quartier: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[OpeningHours] = None
    tags: List[str] = []
    services: List[str] = []
    source_row: Optional[int] = None
    source_label: Optional[str] = None


class AdminCommerceImportRequest(BaseModel):
    items: List[AdminCommerceImportItem]
    auto_activate: bool = True


class CommercePublicResponse(BaseModel):
    """Response for free users - limited info"""
    id: str
    name: str
    category: Optional[CategoryResponse]
    description: Optional[str]
    address: Optional[str]
    city: str
    quartier: Optional[str]
    cover_photo: Optional[str]
    photos: List[str]
    tags: List[str]
    rating_avg: float
    total_reviews: int
    is_open_now: bool
    distance_km: Optional[float] = None
    # Premium fields hidden
    phone: Optional[str] = None  # hidden for free users
    whatsapp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"from_attributes": True}


class CommercePremiumResponse(CommercePublicResponse):
    """Full response for premium users"""
    phone: Optional[str]
    whatsapp: Optional[str]
    latitude: float
    longitude: float
    opening_hours: Optional[Dict[str, Any]]


class CommerceAdminResponse(CommercePremiumResponse):
    id: str
    status: str
    view_count: int
    click_call_count: int
    is_featured: bool
    created_at: datetime


# ── Search / Geo Schemas ───────────────────────────────────────────────────────

class NearbySearchRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 5.0
    category_slug: Optional[str] = None
    query: Optional[str] = None
    open_now: Optional[bool] = None
    page: int = 1
    limit: int = 20


class SearchResponse(BaseModel):
    results: List[CommercePublicResponse]
    total: int
    page: int
    limit: int
    has_more: bool


# ── Subscription Schemas ───────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    payment_provider: str  # wave, orange_money, stripe
    payment_ref: Optional[str] = None


class SubscriptionResponse(BaseModel):
    id: str
    status: str
    plan: str
    price_fcfa: int
    starts_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


# ── Review Schemas ─────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("La note doit être entre 1 et 5")
        return v


class ReviewResponse(BaseModel):
    id: str
    user: UserResponse
    rating: int
    comment: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Event Schemas ──────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    city: str
    quartier: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    is_free: bool = True
    price_fcfa: int = 0
    organizer_name: Optional[str] = None
    tags: List[str] = []


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    cover_image: Optional[str]
    city: str
    quartier: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    starts_at: datetime
    ends_at: Optional[datetime]
    is_free: bool
    price_fcfa: int
    organizer_name: Optional[str]
    tags: List[str]

    model_config = {"from_attributes": True}


# ── AI Assistant Schemas ───────────────────────────────────────────────────────

class AISearchRequest(BaseModel):
    query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: str = "fr"
    conversation_history: List[str] = Field(default_factory=list)


class AISearchResponse(BaseModel):
    interpretation: str
    category_suggestion: Optional[str]
    search_keywords: List[str]
    results: List[CommercePublicResponse]
    ai_message: str


# ── Notification Schemas ───────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: str
    title: str
    body: str
    type: str
    data: Dict
    is_read: bool
    sent_at: datetime

    model_config = {"from_attributes": True}


# ── Admin Schemas ──────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_users: int
    total_premium_users: int
    total_merchants: int
    total_commerces: int
    pending_commerces: int
    total_revenue_fcfa: int
    monthly_revenue_fcfa: int
    total_events: int
    active_ads: int


class PaginationResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int


# ── Surveyor Schemas ──────────────────────────────────────────────────────────

class SurveyPhotoCreate(BaseModel):
    photo_url: str
    photo_type: str = "storefront"


class SurveyCreate(BaseModel):
    store_name: str
    owner_name: Optional[str] = None
    category_id: str
    subcategory_id: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: str
    quartier: Optional[str] = None
    latitude: float
    longitude: float
    gps_accuracy: Optional[float] = None
    description: Optional[str] = None
    opening_hours: Optional[OpeningHours] = None
    availability: Optional[str] = None
    services: List[str] = []
    tags: List[str] = []
    photos: List[SurveyPhotoCreate] = []


class SurveyResponse(BaseModel):
    id: str
    store_name: str
    owner_name: Optional[str]
    category_id: str
    phone: Optional[str]
    address: Optional[str]
    city: str
    quartier: Optional[str]
    latitude: float
    longitude: float
    status: str
    survey_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SurveyorResponse(BaseModel):
    id: str
    surveyor_code: str
    region: Optional[str]
    city: Optional[str]
    quartier: Optional[str]
    is_active: bool
    total_stores_surveyed: int
    verification_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class SurveyorCreate(BaseModel):
    region: Optional[str] = None
    city: Optional[str] = None
    quartier: Optional[str] = None


# ── Store Photo Schemas ────────────────────────────────────────────────────────

class StorePhotoCreate(BaseModel):
    photo_url: str
    photo_type: str = "storefront"
    is_cover: bool = False


class StorePhotoResponse(BaseModel):
    id: str
    commerce_id: str
    photo_url: str
    photo_type: str
    is_cover: bool
    display_order: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ── Category Enhancement Schemas ───────────────────────────────────────────────

class CategoryImageCreate(BaseModel):
    image_url: str
    image_type: str = "cover"
    display_order: int = 0


class CategoryResponseEnhanced(BaseModel):
    id: str
    name: str
    slug: str
    icon: Optional[str]
    color: Optional[str]
    description: Optional[str]
    parent_id: Optional[str]
    sort_order: int
    images: List[Dict] = []

    model_config = {"from_attributes": True}


# ── Advertisement Schemas ──────────────────────────────────────────────────────

class PromotionalOfferCreate(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    discount_percent: Optional[int] = None
    discount_amount_fcfa: Optional[int] = None
    code: Optional[str] = None
    starts_at: datetime
    ends_at: datetime


class PromotionalOfferResponse(BaseModel):
    id: str
    commerce_id: str
    title: str
    description: Optional[str]
    image_url: Optional[str]
    discount_percent: Optional[int]
    discount_amount_fcfa: Optional[int]
    code: Optional[str]
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    view_count: int
    click_count: int
    usage_count: int

    model_config = {"from_attributes": True}


class AdvertisementSpotResponse(BaseModel):
    id: str
    placement: str
    position: int
    width: int
    height: int
    is_available: bool

    model_config = {"from_attributes": True}


# ── Role & Permission Schemas ──────────────────────────────────────────────────

class RolePermissionCreate(BaseModel):
    permission: str
    is_granted: bool = True


class RolePermissionResponse(BaseModel):
    id: str
    permission: str
    is_granted: bool

    model_config = {"from_attributes": True}


class AdminRoleCreate(BaseModel):
    name: str
    role_type: str
    description: Optional[str] = None
    permissions: List[RolePermissionCreate] = []


class AdminRoleResponse(BaseModel):
    id: str
    name: str
    role_type: str
    description: Optional[str]
    is_custom: bool
    permissions: List[RolePermissionResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Audit Log Schemas ──────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    admin_id: str
    action: str
    resource_type: str
    resource_id: str
    changes: Optional[Dict] = None
    status: str
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
