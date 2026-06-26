"""
Shop management endpoints (seller).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models.models import Shop, SellerRequisites, TaxRegime, User
from app.schemas.schemas import (
    ShopCreate, ShopOut, ShopUpdate,
    ShopCreateWithRequisites, SellerRequisitesCreate, SellerRequisitesOut,
    ProductListOut,
)
from app.services import shop_follow_service

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get("/following", response_model=list[ShopOut])
async def list_followed_shops(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shops the current user follows."""
    return await shop_follow_service.followed_shops(db, current_user.id)


@router.get("/feed", response_model=list[ProductListOut])
async def followed_shops_feed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent products from shops the user follows."""
    products = await shop_follow_service.feed(db, current_user.id, limit=24)
    return [ProductListOut.model_validate(p) for p in products]


@router.post("/{shop_id}/follow")
async def follow_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    await shop_follow_service.follow(db, current_user.id, shop_id)
    await db.commit()
    count = await shop_follow_service.follower_count(db, shop_id)
    return {"following": True, "followers": count}


@router.delete("/{shop_id}/follow")
async def unfollow_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await shop_follow_service.unfollow(db, current_user.id, shop_id)
    await db.commit()
    count = await shop_follow_service.follower_count(db, shop_id)
    return {"following": False, "followers": count}


@router.get("/{shop_id}/follow-status")
async def follow_status(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "following": await shop_follow_service.is_following(db, current_user.id, shop_id),
        "followers": await shop_follow_service.follower_count(db, shop_id),
    }


@router.post("", response_model=ShopOut, status_code=status.HTTP_201_CREATED)
async def create_shop(
    payload: ShopCreateWithRequisites,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Create the seller's shop together with their tax requisites. Requisites are
    mandatory and validated per tax regime (self-employed / ИП / ООО). The shop
    starts in 'pending' moderation status.
    """
    result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a shop")

    shop = Shop(owner_id=current_user.id, name=payload.name, description=payload.description)
    db.add(shop)
    await db.flush()

    req = payload.requisites
    requisites = SellerRequisites(
        shop_id=shop.id,
        tax_regime=TaxRegime(req.tax_regime),
        legal_name=req.legal_name,
        inn=req.inn,
        ogrn=req.ogrn,
        kpp=req.kpp,
        legal_address=req.legal_address,
        bank_account=req.bank_account,
        bank_name=req.bank_name,
        bik=req.bik,
        corr_account=req.corr_account,
        vat_code=req.vat_code,
        tax_system_code=req.tax_system_code,
    )
    db.add(requisites)
    await db.commit()
    await db.refresh(shop)
    return shop


@router.get("/my/requisites", response_model=SellerRequisitesOut)
async def get_my_requisites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    req = (await db.execute(
        select(SellerRequisites).where(SellerRequisites.shop_id == shop.id)
    )).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Реквизиты не заполнены")
    return req


@router.put("/my/requisites", response_model=SellerRequisitesOut)
async def update_my_requisites(
    payload: SellerRequisitesCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = (await db.execute(select(Shop).where(Shop.owner_id == current_user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    req = (await db.execute(
        select(SellerRequisites).where(SellerRequisites.shop_id == shop.id)
    )).scalar_one_or_none()
    if not req:
        # Create if missing
        req = SellerRequisites(shop_id=shop.id, tax_regime=TaxRegime(payload.tax_regime),
                               legal_name=payload.legal_name, inn=payload.inn)
        db.add(req)
    req.tax_regime = TaxRegime(payload.tax_regime)
    req.legal_name = payload.legal_name
    req.inn = payload.inn
    req.ogrn = payload.ogrn
    req.kpp = payload.kpp
    req.legal_address = payload.legal_address
    req.bank_account = payload.bank_account
    req.bank_name = payload.bank_name
    req.bik = payload.bik
    req.corr_account = payload.corr_account
    req.vat_code = payload.vat_code
    req.tax_system_code = payload.tax_system_code
    await db.commit()
    await db.refresh(req)
    return req


@router.get("/my", response_model=ShopOut)
async def get_my_shop(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.put("/my", response_model=ShopOut)
async def update_my_shop(
    payload: ShopUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    await db.commit()
    await db.refresh(shop)
    return shop


@router.get("/{shop_id}", response_model=ShopOut)
async def get_shop(shop_id: int, db: AsyncSession = Depends(get_db)):
    from app.models.models import ShopStatus
    result = await db.execute(
        select(Shop).where(
            Shop.id == shop_id,
            Shop.is_active == True,  # noqa: E712
            Shop.status == ShopStatus.active,
        )
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop
