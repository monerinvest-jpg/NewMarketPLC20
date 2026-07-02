"""
Admin API — Platform ops: campaigns, settings, banners, feature flags, SMS provider.

Split out of the former monolithic admin.py; mounted via the admin hub
(app.api.v1.endpoints.admin), same /admin prefix and RBAC dependencies.
"""
"""
Admin API endpoints. All require moderator or superadmin role.
"""
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_moderator_or_admin, get_current_superadmin, get_current_seller
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.models import (
    BalanceTransaction, BalanceTransactionType, Coupon, FiscalReceipt, FiscalReceiptStatus,
    FiscalReceiptType, Order, OrderItem, OrderStatus,
    Payment, PaymentStatus, Product, ProductStatus, Referral, Report, ReportStatus,
    Review, ReviewStatus, Shop, Transaction, TransactionType, User, UserRole, Category, Setting,
)
from app.schemas.schemas import (
    BulkSettingsUpdate, CouponCreate, CouponOut, DashboardStats,
    FiscalReceiptOut,
    OrderOut, OrderStatusUpdate, ProductModerationUpdate, ProductOut,
    ReportOut, ReportUpdate, SettingOut, SettingUpdate,
    ShopAdminUpdate, ShopOut, UserAdminUpdate, UserOut, CategoryCreate, CategoryOut, CategoryUpdate,
    ReviewOut, ReviewModerationUpdate,
    FeatureFlagOut, FeatureFlagUpsert, UserPermissionsUpdate, AdminBalanceAdjust,
)
from app.services import fiscal_service
from app.services.settings_service import get_all_settings, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import Campaign
    rows = (await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))).scalars().all()
    return [
        {"id": c.id, "title": c.title, "channel": c.channel.value if hasattr(c.channel, "value") else c.channel,
         "subject": c.subject, "status": c.status.value if hasattr(c.status, "value") else c.status,
         "recipients": c.recipients, "sent_count": c.sent_count,
         "created_at": c.created_at.isoformat(), "sent_at": c.sent_at.isoformat() if c.sent_at else None}
        for c in rows
    ]


@router.post("/campaigns/preview")
async def preview_campaign_segment(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.services.campaign_service import preview_count
    return {"count": await preview_count(db, payload.get("segment") or {})}


@router.post("/campaigns", status_code=201)
async def create_campaign(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    import json
    from app.models.models import Campaign, CampaignChannel
    from app.services.campaign_service import preview_count
    if not payload.get("title") or not payload.get("body"):
        raise HTTPException(status_code=400, detail="Заполните название и текст")
    seg = payload.get("segment") or {}
    channel = CampaignChannel.inapp if payload.get("channel") == "inapp" else CampaignChannel.email
    camp = Campaign(
        title=payload["title"], channel=channel, subject=payload.get("subject"),
        body=payload["body"], link=payload.get("link"),
        segment=json.dumps(seg), recipients=await preview_count(db, seg),
        created_by_id=current_user.id,
    )
    db.add(camp)
    await db.commit()
    await db.refresh(camp)
    return {"id": camp.id, "recipients": camp.recipients}


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign_now(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import Campaign, CampaignStatus
    from app.services.audit_service import log_action
    camp = await db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    if camp.status == CampaignStatus.sending:
        raise HTTPException(status_code=400, detail="Кампания уже отправляется")
    camp.status = CampaignStatus.sending
    await log_action(db, current_user.id, "campaign.send", "campaign", camp.id, detail=camp.title)
    await db.commit()
    # Offload to Celery; fall back to inline send if the broker is unavailable.
    try:
        from app.tasks.tasks import send_marketing_campaign
        send_marketing_campaign.delay(camp.id)
    except Exception:  # noqa: BLE001
        from app.services.campaign_service import send_campaign
        await send_campaign(db, camp)
    return {"status": "sending"}


# ─── Products (moderation) ────────────────────────────────────────────────────

@router.get("/settings", response_model=list[SettingOut])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    settings_map = await get_all_settings(db)
    await db.commit()
    return list(settings_map.values())


@router.patch("/settings/{key}", response_model=SettingOut)
async def update_setting(
    key: str,
    payload: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    setting = await set_setting(db, key, payload.value)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.patch("/settings", response_model=list[SettingOut])
async def bulk_update_settings(
    payload: BulkSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    results = []
    for key, value in payload.settings.items():
        s = await set_setting(db, key, value)
        results.append(s)
    await db.commit()
    return results


# ─── Coupons ──────────────────────────────────────────────────────────────────

@router.get("/banners", response_model=list)
async def list_banners_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    from app.schemas.schemas import HomepageBannerOut
    result = await db.execute(select(HomepageBanner).order_by(HomepageBanner.sort_order))
    return [HomepageBannerOut.model_validate(b) for b in result.scalars().all()]


@router.post("/banners", status_code=201)
async def create_banner(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    from app.schemas.schemas import HomepageBannerCreate, HomepageBannerOut
    data = HomepageBannerCreate(**payload)
    banner = HomepageBanner(**data.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return HomepageBannerOut.model_validate(banner)


@router.delete("/banners/{banner_id}", status_code=204)
async def delete_banner(
    banner_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import HomepageBanner
    result = await db.execute(select(HomepageBanner).where(HomepageBanner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    await db.delete(banner)
    await db.commit()


# ─── Seller analytics ──────────────────────────────────────────────────────────

@router.get("/feature-flags", response_model=list[FeatureFlagOut])
async def list_feature_flags(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    from app.models.models import FeatureFlag
    rows = (await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all()
    return rows


@router.put("/feature-flags", response_model=FeatureFlagOut)
async def upsert_feature_flag(
    payload: FeatureFlagUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    from app.models.models import FeatureFlag
    from app.services.audit_service import log_action
    existing = (await db.execute(
        select(FeatureFlag).where(FeatureFlag.key == payload.key)
    )).scalar_one_or_none()
    if existing:
        existing.description = payload.description
        existing.is_enabled = payload.is_enabled
        existing.rollout_percent = payload.rollout_percent
        flag = existing
    else:
        flag = FeatureFlag(**payload.model_dump())
        db.add(flag)
    await log_action(db, current_user.id, "feature_flag.upsert", "feature_flag", None, detail=payload.key)
    await db.commit()
    await db.refresh(flag)
    return flag


@router.delete("/feature-flags/{flag_id}", status_code=204)
async def delete_feature_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    from app.models.models import FeatureFlag
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))).scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    await db.delete(flag)
    await db.commit()


# ─── RBAC: granular permissions ────────────────────────────────────────────────────

@router.get("/sms/status")
async def sms_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Current SMS config (without exposing the raw password) + live balance."""
    from app.services.settings_service import get_setting
    from app.services.sms_service import get_balance

    enabled = (await get_setting(db, "sms_enabled")).lower() == "true"
    login = await get_setting(db, "smsc_login")
    sender = await get_setting(db, "smsc_sender")
    use_apikey = (await get_setting(db, "smsc_use_apikey")).lower() == "true"
    password = await get_setting(db, "smsc_password")

    balance = await get_balance(db) if (login or use_apikey) and password else {
        "ok": False, "balance": None, "currency": None, "error": "Учётные данные не заданы"
    }
    return {
        "enabled": enabled,
        "login": login,
        "sender": sender,
        "use_apikey": use_apikey,
        "has_password": bool(password),
        "notify_order_status": (await get_setting(db, "sms_notify_order_status")).lower() == "true",
        "notify_phone_verification": (await get_setting(db, "sms_notify_phone_verification")).lower() == "true",
        "balance": balance,
    }


@router.put("/sms/settings")
async def update_sms_settings(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Update SMS settings from the dedicated admin section."""
    from app.services.settings_service import set_setting
    from app.services.audit_service import log_action

    allowed = {
        "sms_enabled", "smsc_login", "smsc_password", "smsc_sender",
        "smsc_use_apikey", "sms_notify_order_status", "sms_notify_phone_verification",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        # Don't overwrite the stored password with an empty/masked value
        if key == "smsc_password" and value in ("", None, "********"):
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        await set_setting(db, key, str(value))

    await log_action(db, current_user.id, "sms.settings_update", "settings", None,
                     detail="SMS section updated")
    await db.commit()
    return {"status": "saved"}


@router.post("/sms/test")
async def sms_test(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Send a test SMS to verify credentials (bypasses the enabled gate)."""
    from app.services.sms_service import send_sms
    phone = payload.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Укажите номер телефона")
    text = payload.get("text") or "Тестовое сообщение от маркетплейса"
    result = await send_sms(db, phone, text, purpose="test", force=True)
    await db.commit()
    return result


@router.get("/sms/balance")
async def sms_balance(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """Live SMSC.ru account balance."""
    from app.services.sms_service import get_balance
    return await get_balance(db)


@router.get("/sms/stats")
async def sms_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    """SMS statistics: totals, success rate, spend, breakdown by purpose."""
    from datetime import datetime, timezone, timedelta
    from app.models.models import SmsLog
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (await db.execute(
        select(SmsLog).where(SmsLog.created_at >= cutoff)
    )).scalars().all()

    total = len(rows)
    sent = sum(1 for r in rows if r.status == "sent")
    failed = total - sent
    total_cost = sum(float(r.cost) for r in rows if r.cost is not None)
    total_segments = sum(r.sms_count for r in rows if r.status == "sent")

    by_purpose: dict[str, dict] = {}
    for r in rows:
        p = by_purpose.setdefault(r.purpose, {"sent": 0, "failed": 0, "cost": 0.0})
        if r.status == "sent":
            p["sent"] += 1
            p["cost"] += float(r.cost) if r.cost else 0.0
        else:
            p["failed"] += 1

    return {
        "days": days,
        "total": total,
        "sent": sent,
        "failed": failed,
        "success_rate": round(sent / total * 100, 1) if total else 0.0,
        "total_cost": round(total_cost, 2),
        "total_segments": total_segments,
        "by_purpose": by_purpose,
    }


@router.get("/sms/log")
async def sms_log_view(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """Recent SMS send log."""
    from app.models.models import SmsLog
    query = select(SmsLog)
    if status_filter:
        query = query.where(SmsLog.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.order_by(SmsLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [
            {
                "id": r.id, "phone": r.phone, "purpose": r.purpose,
                "text_preview": r.text_preview, "status": r.status,
                "smsc_id": r.smsc_id, "cost": float(r.cost) if r.cost else None,
                "sms_count": r.sms_count, "error": r.error,
                "created_at": r.created_at.isoformat(),
            } for r in rows
        ],
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }
