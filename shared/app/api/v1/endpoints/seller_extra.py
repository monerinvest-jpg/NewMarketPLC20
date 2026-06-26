"""
Block 6 endpoints: real file upload, seller chat templates, and business hours.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models.models import ChatTemplate, Shop, User
from app.schemas.schemas import (
    BusinessHoursUpdate, ChatTemplateCreate, ChatTemplateOut, FileUploadResponse,
)
from app.services.storage_service import save_file

router = APIRouter(tags=["seller-extra"])


# ─── File upload ───────────────────────────────────────────────────────────────

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image and get back a public URL to use for products, review photos,
    shop logos/banners, etc. Any authenticated user may upload.
    """
    content = await file.read()
    try:
        url = await save_file(content, file.content_type or "", file.filename or "upload")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return FileUploadResponse(url=url, filename=file.filename or "upload")


# ─── Chat templates ────────────────────────────────────────────────────────────

async def _get_shop(db: AsyncSession, user: User) -> Shop:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")
    return shop


@router.get("/seller/chat-templates", response_model=list[ChatTemplateOut])
async def list_chat_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    rows = (await db.execute(
        select(ChatTemplate).where(ChatTemplate.shop_id == shop.id)
        .order_by(ChatTemplate.created_at.desc())
    )).scalars().all()
    return rows


@router.post("/seller/chat-templates", response_model=ChatTemplateOut, status_code=201)
async def create_chat_template(
    payload: ChatTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    tpl = ChatTemplate(shop_id=shop.id, title=payload.title, body=payload.body)
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


@router.delete("/seller/chat-templates/{template_id}", status_code=204)
async def delete_chat_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    tpl = (await db.execute(
        select(ChatTemplate).where(ChatTemplate.id == template_id, ChatTemplate.shop_id == shop.id)
    )).scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    await db.delete(tpl)
    await db.commit()


# ─── Business hours ────────────────────────────────────────────────────────────

@router.put("/seller/business-hours")
async def update_business_hours(
    payload: BusinessHoursUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _get_shop(db, current_user)
    shop.business_hours = payload.business_hours
    await db.commit()
    return {"business_hours": shop.business_hours}
