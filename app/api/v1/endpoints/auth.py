from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, get_current_user
from app.models.models import User, UserRole
from app.services.user_service import UserService, OTPService
from app.schemas.schemas import (
    PhoneRegisterRequest, OTPVerifyRequest, LoginRequest,
    TokenResponse, UserResponse, RefreshRequest, PinSetupRequest
)

router = APIRouter()

LOCAL_ADMIN_PHONE = "+22600000000"
LOCAL_ADMIN_NAME = "Admin YAAR+"


def _build_default_full_name(phone: str) -> str:
    suffix = phone[-4:] if len(phone) >= 4 else phone
    return f"Utilisateur {suffix}"


def _build_token_response(user: User) -> TokenResponse:
    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


async def _ensure_local_admin(db: AsyncSession, user: User, full_name: str | None = None) -> User:
    if not settings.AUTH_SKIP_OTP:
        return user
    if user.phone != LOCAL_ADMIN_PHONE:
        return user
    if full_name and full_name != LOCAL_ADMIN_NAME and user.full_name != LOCAL_ADMIN_NAME:
        return user
    if user.is_admin and user.role == UserRole.ADMIN:
        return user

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            full_name=LOCAL_ADMIN_NAME,
            role=UserRole.ADMIN,
            is_admin=True,
            is_phone_verified=True,
        )
    )
    await db.flush()
    return await UserService.get_by_id(db, user.id)


@router.post("/request-otp")
async def request_otp(data: PhoneRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register phone and optionally configure a PIN."""
    user = await UserService.get_by_phone(db, data.phone)
    if not user:
        user = await UserService.create_user(db, data.phone, data.full_name, data.referral_code)

    if data.pin:
        user = await UserService.set_pin(db, user.id, data.pin)

    user = await _ensure_local_admin(db, user, data.full_name)

    if settings.AUTH_SKIP_OTP:
        if not user.is_phone_verified:
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(is_phone_verified=True)
            )
            await db.flush()
            user = await UserService.get_by_id(db, user.id)

        token_response = _build_token_response(user)

        return {
            "message": "Connexion directe activée" if not data.pin else "Code PIN configuré et connexion réussie",
            "phone": data.phone,
            "is_new_user": user.is_phone_verified is False,
            "otp_skipped": True,
            **token_response.model_dump(mode="json"),
        }

    code = await OTPService.create_otp(db, data.phone)
    await OTPService.send_sms_otp(data.phone, code)

    return {
        "message": f"Code OTP envoyé au {data.phone}",
        "phone": data.phone,
        "is_new_user": user.is_phone_verified is False,
    }


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(data: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Compatibility route: verify OTP or PIN and get tokens."""
    user = await UserService.verify_pin(db, data.phone, data.code)
    if user:
        user = await _ensure_local_admin(db, user)
        if not user.is_phone_verified:
            await db.execute(update(User).where(User.id == user.id).values(is_phone_verified=True))
            await db.flush()
            user = await UserService.get_by_id(db, user.id)
        return _build_token_response(user)

    if settings.AUTH_SKIP_OTP:
        user = await UserService.get_by_phone(db, data.phone)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        if not user.is_phone_verified:
            await db.execute(update(User).where(User.id == user.id).values(is_phone_verified=True))
            await db.flush()
            user = await UserService.get_by_id(db, user.id)
        return _build_token_response(user)

    is_valid = await OTPService.verify_otp(db, data.phone, data.code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code PIN invalide",
        )

    user = await UserService.get_by_phone(db, data.phone)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if not user.is_phone_verified:
        await db.execute(update(User).where(User.id == user.id).values(is_phone_verified=True))
        await db.flush()
        user = await UserService.get_by_id(db, user.id)

    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await UserService.get_by_phone(db, data.phone)

    if not user:
        if not settings.AUTH_SKIP_OTP:
            raise HTTPException(status_code=400, detail="Numéro ou code PIN invalide")

        user = await UserService.create_user(
            db,
            data.phone,
            _build_default_full_name(data.phone),
        )
        user = await UserService.set_pin(db, user.id, data.pin)
    elif not user.password_hash:
        if not settings.AUTH_SKIP_OTP:
            raise HTTPException(status_code=400, detail="Numéro ou code PIN invalide")

        user = await UserService.set_pin(db, user.id, data.pin)
    else:
        user = await UserService.verify_pin(db, data.phone, data.pin)
        if not user:
            raise HTTPException(status_code=400, detail="Numéro ou code PIN invalide")

    user = await _ensure_local_admin(db, user)

    if not user.is_phone_verified:
        await db.execute(update(User).where(User.id == user.id).values(is_phone_verified=True))
        await db.flush()
        user = await UserService.get_by_id(db, user.id)

    return _build_token_response(user)


@router.post("/set-pin", response_model=UserResponse)
async def set_pin(data: PinSetupRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    user = await UserService.set_pin(db, current_user.id, data.pin)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de rafraîchissement invalide")

    user = await UserService.get_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    access_token = create_access_token({"sub": user.id})
    refresh_token_new = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    # In production: blacklist token in Redis
    return {"message": "Déconnexion réussie"}
