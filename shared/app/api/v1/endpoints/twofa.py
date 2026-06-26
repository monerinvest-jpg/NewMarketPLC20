"""
Item 8 endpoints: two-factor authentication (TOTP) setup and management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import TwoFASetupOut, TwoFAVerifyRequest
from app.services import twofa_service

router = APIRouter(prefix="/2fa", tags=["2fa"])


@router.post("/setup", response_model=TwoFASetupOut)
async def setup_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Begin 2FA enrollment: generate a secret + backup codes and return the
    otpauth URL. 2FA is not active until /2fa/verify confirms a code. The secret
    is stored provisionally; is_2fa_enabled stays false until verification.
    """
    secret = twofa_service.generate_secret()
    backup_codes = twofa_service.generate_backup_codes()
    current_user.totp_secret = secret
    current_user.totp_backup_codes = twofa_service.hash_backup_codes(backup_codes)
    current_user.is_2fa_enabled = False
    await db.commit()
    return TwoFASetupOut(
        secret=secret,
        otpauth_url=twofa_service.get_otpauth_url(secret, current_user.email),
        backup_codes=backup_codes,
    )


@router.post("/verify")
async def verify_2fa(
    payload: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm a TOTP code to activate 2FA on the account."""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Сначала вызовите /2fa/setup")
    if not twofa_service.verify_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Неверный код")
    current_user.is_2fa_enabled = True
    await db.commit()
    return {"status": "enabled"}


@router.post("/disable")
async def disable_2fa(
    payload: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable 2FA (requires a valid current code)."""
    if not current_user.is_2fa_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не включена")
    if not twofa_service.verify_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Неверный код")
    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    current_user.totp_backup_codes = None
    await db.commit()
    return {"status": "disabled"}


@router.get("/status")
async def status_2fa(current_user: User = Depends(get_current_user)):
    return {"enabled": current_user.is_2fa_enabled}
