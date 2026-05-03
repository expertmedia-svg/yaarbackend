from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
import random
import string
from datetime import datetime, timedelta, timezone

from app.models.models import User, OTPCode
from app.core.security import get_password_hash, verify_password
from app.schemas.schemas import UserUpdate


class UserService:

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    @staticmethod
    def generate_referral_code(length: int = 8) -> str:
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

    @staticmethod
    async def create_user(db: AsyncSession, phone: str, full_name: str, referral_code: Optional[str] = None) -> User:
        # Find referrer
        referrer_id = None
        if referral_code:
            ref_result = await db.execute(select(User).where(User.referral_code == referral_code))
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referrer_id = referrer.id

        user = User(
            phone=phone,
            full_name=full_name,
            referral_code=UserService.generate_referral_code(),
            referred_by=referrer_id,
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> Optional[User]:
        update_data = data.model_dump(exclude_none=True)
        if update_data:
            await db.execute(
                update(User).where(User.id == user_id).values(**update_data)
            )
            await db.flush()
        return await UserService.get_by_id(db, user_id)

    @staticmethod
    async def set_premium(db: AsyncSession, user_id: str, is_premium: bool):
        await db.execute(
            update(User).where(User.id == user_id).values(is_premium=is_premium)
        )
        await db.flush()

    @staticmethod
    async def set_pin(db: AsyncSession, user_id: str, pin: str) -> Optional[User]:
        await db.execute(
            update(User).where(User.id == user_id).values(password_hash=get_password_hash(pin))
        )
        await db.flush()
        return await UserService.get_by_id(db, user_id)

    @staticmethod
    async def verify_pin(db: AsyncSession, phone: str, pin: str) -> Optional[User]:
        user = await UserService.get_by_phone(db, phone)
        if not user or not user.password_hash:
            return None
        if not verify_password(pin, user.password_hash):
            return None
        return user


class OTPService:

    @staticmethod
    def generate_otp() -> str:
        return "".join(random.choices(string.digits, k=6))

    @staticmethod
    async def create_otp(db: AsyncSession, phone: str) -> str:
        # Invalidate previous OTPs
        await db.execute(
            update(OTPCode)
            .where(OTPCode.phone == phone, OTPCode.is_used == False)
            .values(is_used=True)
        )
        code = OTPService.generate_otp()
        otp = OTPCode(
            phone=phone,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(otp)
        await db.flush()
        return code

    @staticmethod
    async def verify_otp(db: AsyncSession, phone: str, code: str) -> bool:
        result = await db.execute(
            select(OTPCode).where(
                OTPCode.phone == phone,
                OTPCode.code == code,
                OTPCode.is_used == False,
                OTPCode.expires_at > datetime.now(timezone.utc),
            )
        )
        otp = result.scalar_one_or_none()
        if not otp:
            return False
        await db.execute(
            update(OTPCode).where(OTPCode.id == otp.id).values(is_used=True)
        )
        return True

    @staticmethod
    async def send_sms_otp(phone: str, code: str):
        """Send OTP via SMS provider (Orange, Wave, etc.)"""
        # In production: integrate with Orange API, Africa's Talking, etc.
        # For now, just log
        print(f"[OTP] Sending {code} to {phone}")
        # TODO: implement actual SMS sending
