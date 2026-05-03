from sqlalchemy import (
    Column, String, Boolean, Float, Integer, Text, Table,
    ForeignKey, DateTime, Enum, JSON, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


user_admin_roles = Table(
    "user_admin_roles",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("admin_role_id", String, ForeignKey("admin_roles.id"), primary_key=True),
)


class UserRole(str, enum.Enum):
    USER = "user"
    MERCHANT = "merchant"
    SURVEYOR = "surveyor"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    REGIONAL_ADMIN = "regional_admin"
    SUPERVISOR = "supervisor"
    MODERATOR = "moderator"
    SUPPORT = "support"
    FINANCE = "finance"
    MARKETING = "marketing"
    AD_MANAGER = "ad_manager"
    EVENT_MANAGER = "event_manager"


class CommerceStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AdStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


# ── Users ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    referral_code = Column(String(10), unique=True, nullable=True)
    referred_by = Column(String, ForeignKey("users.id"), nullable=True)
    fcm_token = Column(String, nullable=True)  # Firebase push token
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    subscriptions = relationship("Subscription", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    admin_roles = relationship("AdminRole", secondary=user_admin_roles, back_populates="users")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Categories ─────────────────────────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    icon = Column(String(50), nullable=True)   # emoji or icon name
    color = Column(String(7), nullable=True)   # hex color
    description = Column(Text, nullable=True)
    parent_id = Column(String, ForeignKey("categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    commerces = relationship("Commerce", back_populates="category")
    children = relationship("Category")


# ── Merchants & Commerces ──────────────────────────────────────────────────────

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    business_name = Column(String(150), nullable=False)
    is_verified = Column(Boolean, default=False)
    rating_avg = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    commerces = relationship("Commerce", back_populates="merchant")


class Commerce(Base):
    __tablename__ = "commerces"

    id = Column(String, primary_key=True, default=gen_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)

    name = Column(String(150), nullable=False, index=True)
    slug = Column(String(150), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    whatsapp = Column(String(20), nullable=True)
    address = Column(String(250), nullable=True)
    city = Column(String(100), nullable=True)
    quartier = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    cover_photo = Column(String, nullable=True)
    photos = Column(JSON, default=list)  # list of URLs

    opening_hours = Column(JSON, nullable=True)  # {"mon": ["08:00", "18:00"], ...}
    is_open_now = Column(Boolean, default=True)  # computed / cached
    tags = Column(JSON, default=list)  # ["halal", "livraison", etc.]
    services = Column(JSON, default=list)

    status = Column(Enum(CommerceStatus), default=CommerceStatus.PENDING)
    is_featured = Column(Boolean, default=False)
    is_premium_listing = Column(Boolean, default=False)

    view_count = Column(BigInteger, default=0)
    click_call_count = Column(Integer, default=0)
    click_whatsapp_count = Column(Integer, default=0)

    rating_avg = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    merchant = relationship("Merchant", back_populates="commerces")
    category = relationship("Category", back_populates="commerces")
    reviews = relationship("Review", back_populates="commerce")
    favorites = relationship("Favorite", back_populates="commerce")


# ── Subscriptions ──────────────────────────────────────────────────────────────

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    plan = Column(String(50), default="premium_monthly")
    price_fcfa = Column(Integer, default=100)
    payment_provider = Column(String(50), nullable=True)  # stripe, wave, orange_money
    payment_ref = Column(String, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="subscriptions")


# ── Reviews ────────────────────────────────────────────────────────────────────

class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reviews")
    commerce = relationship("Commerce", back_populates="reviews")


# ── Favorites ──────────────────────────────────────────────────────────────────

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="favorites")
    commerce = relationship("Commerce", back_populates="favorites")


# ── Events ─────────────────────────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cover_image = Column(String, nullable=True)
    city = Column(String(100), nullable=True)
    quartier = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    is_free = Column(Boolean, default=True)
    price_fcfa = Column(Integer, default=0)
    organizer_name = Column(String(150), nullable=True)
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Advertisements ─────────────────────────────────────────────────────────────

class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(String, primary_key=True, default=gen_uuid)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=True)
    title = Column(String(200), nullable=False)
    image_url = Column(String, nullable=True)
    cta_text = Column(String(50), nullable=True)
    cta_url = Column(String, nullable=True)
    placement = Column(String(50), default="home_banner")  # home_banner, search_top, category_top
    city_target = Column(String(100), nullable=True)
    status = Column(Enum(AdStatus), default=AdStatus.PENDING)
    budget_fcfa = Column(Integer, default=0)
    spent_fcfa = Column(Integer, default=0)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Notifications ──────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String(50), default="info")  # info, promo, alert, system
    data = Column(JSON, default=dict)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Support Tickets ────────────────────────────────────────────────────────────

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="open")  # open, in_progress, resolved, closed
    priority = Column(String(20), default="normal")
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ── Surveyor / Field Agents ────────────────────────────────────────────────────

class Surveyor(Base):
    __tablename__ = "surveyors"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    surveyor_code = Column(String(20), unique=True, nullable=False, index=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    quartier = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    sync_status = Column(String(20), default="synced")  # synced, pending_sync, offline
    last_sync = Column(DateTime(timezone=True), nullable=True)
    total_stores_surveyed = Column(Integer, default=0)
    verification_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    surveys = relationship("Survey", back_populates="surveyor")


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(String, primary_key=True, default=gen_uuid)
    surveyor_id = Column(String, ForeignKey("surveyors.id"), nullable=False)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=True)

    store_name = Column(String(150), nullable=False)
    owner_name = Column(String(150), nullable=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(String, nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(250), nullable=True)
    city = Column(String(100), nullable=True)
    quartier = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    gps_accuracy = Column(Float, nullable=True)

    description = Column(Text, nullable=True)
    opening_hours = Column(JSON, nullable=True)
    availability = Column(String(100), nullable=True)
    services = Column(JSON, default=list)
    tags = Column(JSON, default=list)

    status = Column(String(20), default="pending")  # pending, verified, rejected, merged
    is_active = Column(Boolean, default=True)
    survey_date = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    surveyor = relationship("Surveyor", back_populates="surveys")
    category = relationship("Category")
    photos = relationship("SurveyPhoto", back_populates="survey")


class SurveyPhoto(Base):
    __tablename__ = "survey_photos"

    id = Column(String, primary_key=True, default=gen_uuid)
    survey_id = Column(String, ForeignKey("surveys.id"), nullable=False)
    photo_url = Column(String, nullable=False)
    photo_type = Column(String(50), default="storefront")  # storefront, interior, signage, food, etc.
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    survey = relationship("Survey", back_populates="photos")


# ── Store Photos ───────────────────────────────────────────────────────────────

class StorePhoto(Base):
    __tablename__ = "store_photos"

    id = Column(String, primary_key=True, default=gen_uuid)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=False)
    photo_url = Column(String, nullable=False)
    photo_type = Column(String(50), default="storefront")  # storefront, interior, signage, food, menu, ambiance
    is_cover = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    commerce = relationship("Commerce")
    uploader = relationship("User")


# ── Category Enhancement ───────────────────────────────────────────────────────

class CategoryImage(Base):
    __tablename__ = "category_images"

    id = Column(String, primary_key=True, default=gen_uuid)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    image_url = Column(String, nullable=False)
    image_type = Column(String(50), default="cover")  # cover, icon, banner
    display_order = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category")


# ── Advertisement Management ───────────────────────────────────────────────────

class AdvertisementSpot(Base):
    __tablename__ = "advertisement_spots"

    id = Column(String, primary_key=True, default=gen_uuid)
    placement = Column(String(100), nullable=False, index=True)  # home_banner, category_top, nearby_promotions, search_top
    position = Column(Integer, default=0)
    width = Column(Integer, default=360)
    height = Column(Integer, default=200)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PromotionalOffer(Base):
    __tablename__ = "promotional_offers"

    id = Column(String, primary_key=True, default=gen_uuid)
    commerce_id = Column(String, ForeignKey("commerces.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    discount_percent = Column(Integer, nullable=True)
    discount_amount_fcfa = Column(Integer, nullable=True)
    code = Column(String(50), unique=True, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    view_count = Column(BigInteger, default=0)
    click_count = Column(BigInteger, default=0)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    commerce = relationship("Commerce")


# ── Role & Permissions ─────────────────────────────────────────────────────────

class AdminRole(Base):
    __tablename__ = "admin_roles"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), unique=True, nullable=False)
    role_type = Column(Enum(UserRole), nullable=False)
    description = Column(Text, nullable=True)
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    permissions = relationship("RolePermission", back_populates="role")
    users = relationship("User", secondary=user_admin_roles, back_populates="admin_roles")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(String, primary_key=True, default=gen_uuid)
    admin_role_id = Column(String, ForeignKey("admin_roles.id"), nullable=False)
    permission = Column(String(100), nullable=False)  # commerce.create, commerce.edit, user.ban, admin.logs, etc.
    is_granted = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = relationship("AdminRole", back_populates="permissions")


# ── Audit Logs ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    admin_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # create, update, delete, ban, verify, etc.
    resource_type = Column(String(100), nullable=False)  # commerce, user, category, advertisement
    resource_id = Column(String, nullable=False)
    changes = Column(JSON, nullable=True)
    status = Column(String(50), default="success")  # success, failure, pending
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    admin = relationship("User")
