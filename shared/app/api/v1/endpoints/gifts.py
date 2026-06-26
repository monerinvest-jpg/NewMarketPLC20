"""
Gift-certificate & promo-balance endpoints.
- Buyer: purchase a certificate, redeem a code, view promo balance & history.
- Admin: issue promo certificates and list them.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_moderator_or_admin, get_current_user
from app.core.database import get_db
from app.models.models import GiftCertificate, User
from app.schemas.schemas import (
    AdminGiftIssue, GiftCertificateOut, GiftPurchase, GiftRedeem,
)
from app.services import gift_service

router = APIRouter(prefix="/gift-certificates", tags=["gift-certificates"])
admin_router = APIRouter(prefix="/admin/gift-certificates", tags=["gift-certificates-admin"])


@router.post("/purchase", response_model=GiftCertificateOut)
async def purchase_certificate(
    payload: GiftPurchase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cert = await gift_service.purchase(
            db, current_user, payload.amount, payload.recipient_email, payload.message
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(cert)
    return cert


@router.post("/redeem")
async def redeem_certificate(
    payload: GiftRedeem,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        amount = await gift_service.redeem(db, current_user, payload.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"credited": str(amount), "promo_balance": str(current_user.promo_balance)}


@router.get("/promo-balance")
async def promo_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await gift_service.overview(db, current_user)


@admin_router.post("", response_model=list[GiftCertificateOut])
async def admin_issue(
    payload: AdminGiftIssue,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    certs = await gift_service.issue(db, payload.amount, payload.count, payload.expires_at, payload.message)
    await db.commit()
    for c in certs:
        await db.refresh(c)
    return certs


@admin_router.get("", response_model=list[GiftCertificateOut])
async def admin_list(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    rows = (await db.execute(
        select(GiftCertificate).order_by(GiftCertificate.created_at.desc()).limit(200)
    )).scalars().all()
    return list(rows)
