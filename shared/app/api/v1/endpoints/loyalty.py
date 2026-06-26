"""
Loyalty-program endpoints.
- Buyer: current tier status (progress, perks, downgrade countdown), tier ladder.
- Admin: configure tiers (thresholds, cashback, perks, retention).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_moderator_or_admin, get_current_user
from app.core.database import get_db
from app.models.models import LoyaltyTier, User
from app.schemas.schemas import LoyaltyTierCreate, LoyaltyTierOut, LoyaltyTierUpdate
from app.services import loyalty_tier_service

router = APIRouter(prefix="/loyalty", tags=["loyalty"])
admin_router = APIRouter(prefix="/admin/loyalty-tiers", tags=["loyalty-admin"])


@router.get("/me")
async def my_loyalty(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await loyalty_tier_service.ensure_default_tiers(db)
    status = await loyalty_tier_service.user_status(db, current_user)
    await db.commit()
    return status


@router.get("/tiers", response_model=list[LoyaltyTierOut])
async def list_tiers(db: AsyncSession = Depends(get_db)):
    await loyalty_tier_service.ensure_default_tiers(db)
    await db.commit()
    rows = (await db.execute(
        select(LoyaltyTier).where(LoyaltyTier.is_active == True).order_by(LoyaltyTier.level)  # noqa: E712
    )).scalars().all()
    return list(rows)


# ─── Admin ───

@admin_router.get("", response_model=list[LoyaltyTierOut])
async def admin_list(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    await loyalty_tier_service.ensure_default_tiers(db)
    await db.commit()
    rows = (await db.execute(select(LoyaltyTier).order_by(LoyaltyTier.level))).scalars().all()
    return list(rows)


@admin_router.post("", response_model=LoyaltyTierOut)
async def admin_create(
    payload: LoyaltyTierCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    exists = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.key == payload.key))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Уровень с таким ключом уже есть")
    tier = LoyaltyTier(**payload.model_dump())
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return tier


@admin_router.patch("/{tier_id}", response_model=LoyaltyTierOut)
async def admin_update(
    tier_id: int,
    payload: LoyaltyTierUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == tier_id))).scalar_one_or_none()
    if not tier:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tier, k, v)
    await db.commit()
    await db.refresh(tier)
    return tier


@admin_router.delete("/{tier_id}", status_code=204)
async def admin_delete(
    tier_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == tier_id))).scalar_one_or_none()
    if tier:
        await db.delete(tier)
        await db.commit()
