from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import secrets


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # App
    APP_NAME: str = "YAAR+"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = secrets.token_urlsafe(32)
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'yaar.db').as_posix()}"

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "https://admin.yaarplus.com",
        "https://app.yaarplus.com",
    ]

    # File Upload
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    UPLOAD_DIR: str = "uploads"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: str = "eu-west-1"

    # Firebase (Push Notifications)
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    # OpenAI (AI Assistant)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Stripe / Payment
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Premium Pricing
    PREMIUM_PRICE_FCFA: int = 100
    PREMIUM_PRICE_STRIPE_CENTS: int = 18  # ~100 FCFA

    # SMS OTP
    SMS_PROVIDER: str = "orange"  # orange, wave, africatalk
    SMS_API_KEY: Optional[str] = None
    SMS_SENDER: str = "YAAR+"
    AUTH_SKIP_OTP: bool = True

    # Geolocation
    MAX_SEARCH_RADIUS_KM: float = 50.0
    DEFAULT_SEARCH_RADIUS_KM: float = 5.0

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", "warn", "warning", "info", "error", "debug"}:
                return False
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("sqlite+aiosqlite:///./"):
            relative_path = value.removeprefix("sqlite+aiosqlite:///./")
            return f"sqlite+aiosqlite:///{(BASE_DIR / relative_path).as_posix()}"
        if value.startswith("sqlite:///./"):
            relative_path = value.removeprefix("sqlite:///./")
            return f"sqlite+aiosqlite:///{(BASE_DIR / relative_path).as_posix()}"
        if value.startswith("sqlite:///") and not value.startswith("sqlite+aiosqlite:///"):
            return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return value

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
