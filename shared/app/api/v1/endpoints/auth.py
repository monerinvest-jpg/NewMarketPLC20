"""
Authentication endpoints: register, login, refresh, me, password reset.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token,
    get_password_hash, verify_password, verify_token,
)
from app.models.models import PasswordResetToken, User, VerificationPurpose
from app.schemas.schemas import (
    LoginRequest, PasswordResetConfirm, PasswordResetRequest,
    Token, TokenRefresh, UserCreate, UserOut,
    VerifyCodeRequest, ResendCodeRequest, VerifyPhoneRequest,
)
from app.services.email_service import send_password_reset_email, send_verification_code_email
from app.services.verification_service import issue_code, verify_code
from app.services.referral_service import ensure_referral_code, register_referral
from app.api.v1.deps import get_current_user
from app.core.ratelimit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user. Optionally accepts a referral code."""
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
    )
    db.add(user)
    await db.flush()

    await ensure_referral_code(user, db)

    if payload.referral_code:
        await register_referral(user, payload.referral_code, db)

    # Issue an email verification code and send it. The account is created but
    # email_verified stays False until the user confirms the code.
    code = await issue_code(db, user, VerificationPurpose.email, user.email)
    await db.commit()
    await db.refresh(user)
    try:
        await send_verification_code_email(user.email, code)
    except Exception:
        # Don't fail registration if email delivery hiccups; user can resend.
        pass
    return user


@router.post("/verify-email")
async def verify_email(payload: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    """Confirm a registration email with the code that was sent."""
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.email_verified:
        return {"status": "already_verified"}
    ok, error = await verify_code(db, user, VerificationPurpose.email, payload.code)
    await db.commit()
    if not ok:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "verified"}


@router.post("/resend-code")
@limiter.limit("3/minute")
async def resend_code(request: Request, payload: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Resend an email verification code (rate-limited)."""
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user:
        # Don't reveal whether the email exists
        return {"status": "sent"}
    if user.email_verified:
        return {"status": "already_verified"}
    code = await issue_code(db, user, VerificationPurpose.email, user.email)
    await db.commit()
    try:
        await send_verification_code_email(user.email, code)
    except Exception:
        pass
    return {"status": "sent"}


@router.post("/send-phone-code")
@limiter.limit("3/minute")
async def send_phone_code(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send an SMS code to confirm the current user's phone. Requires SMS to be
    enabled in admin and a phone on the account.
    """
    from app.services.sms_service import is_enabled as sms_is_enabled, send_sms
    if not await sms_is_enabled(db):
        raise HTTPException(status_code=400, detail="SMS-подтверждение временно недоступно")
    if not current_user.phone:
        raise HTTPException(status_code=400, detail="Добавьте номер телефона в профиле")

    code = await issue_code(db, current_user, VerificationPurpose.phone, current_user.phone)
    result = await send_sms(
        db, current_user.phone, f"Код подтверждения: {code}",
        purpose="phone_verification",
    )
    await db.commit()
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error") or "Не удалось отправить SMS")
    return {"status": "sent"}


@router.post("/verify-phone")
async def verify_phone(
    payload: VerifyPhoneRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm the user's phone with the SMS code."""
    ok, error = await verify_code(db, current_user, VerificationPurpose.phone, payload.code)
    await db.commit()
    if not ok:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "verified"}


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    # Two-factor: if enabled, require a valid TOTP code or a backup code.
    if user.is_2fa_enabled and user.totp_secret:
        from app.services import twofa_service
        code = (payload.totp_code or "").strip()
        if not code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="2FA_REQUIRED")
        ok = twofa_service.verify_code(user.totp_secret, code)
        if not ok:
            consumed, new_store = twofa_service.consume_backup_code(user.totp_backup_codes, code)
            if consumed:
                user.totp_backup_codes = new_store
                await db.commit()
                ok = True
        if not ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный код 2FA")

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
async def refresh(payload: TokenRefresh, db: AsyncSession = Depends(get_db)):
    user_id = verify_token(payload.refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def forgot_password(request: Request, payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """
    Always returns success regardless of whether the email exists, to avoid
    leaking which addresses are registered. If the email exists, any prior
    unused token is invalidated and a fresh one-hour token is issued.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        # Invalidate any previous unused tokens for this user
        old_tokens = (await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,  # noqa: E712
            )
        )).scalars().all()
        for t in old_tokens:
            t.used = True

        token_value = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_token)
        await db.commit()

        await send_password_reset_email(user.email, token_value, settings.FRONTEND_URL)

    return {"message": "Если такой email зарегистрирован, на него отправлена ссылка для восстановления пароля"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == payload.token)
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token or reset_token.used:
        raise HTTPException(status_code=400, detail="Недействительная или уже использованная ссылка")
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Срок действия ссылки истёк, запросите новую")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь не найден")

    user.password_hash = get_password_hash(payload.new_password)
    reset_token.used = True
    await db.commit()

    return {"message": "Пароль успешно изменён"}
