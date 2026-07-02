"""
VK Market import — seller-facing endpoints.

Flow:
  GET  /seller/integrations/vk/status      → configured? connected?
  GET  /seller/integrations/vk/auth-url    → OAuth URL (state = signed user token)
  GET  /seller/integrations/vk/callback    → VK redirect: exchange code, store token
  GET  /seller/integrations/vk/communities → seller's admin communities
  POST /seller/integrations/vk/preview     → normalized market items of a community
  POST /seller/integrations/vk/import      → queue the Celery import, returns task id
  GET  /seller/integrations/vk/import/{id} → task progress/result

The callback carries no Authorization header (browser redirect from VK), so the
seller's identity travels in `state` as a short-lived signed access token.
"""
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_token
from app.models.models import Shop, ShopIntegration, User
from app.services import vk_client, vk_import_service

router = APIRouter(prefix="/seller/integrations/vk", tags=["vk-import"])


async def _my_shop(user: User, db: AsyncSession) -> Shop:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=400, detail="Сначала создайте магазин")
    return shop


def _seller_cabinet_url(path: str = "/import") -> str:
    """seller.<домен> из FRONTEND_URL (кабинет продавца живёт на поддомене)."""
    parts = urlparse(settings.FRONTEND_URL)
    host = parts.netloc
    if not host.startswith("seller."):
        host = "seller." + host
    return urlunparse((parts.scheme, host, path, "", "", ""))


class PreviewRequest(BaseModel):
    community_id: int


class ImportRequest(BaseModel):
    community_id: int
    category_id: int
    # Пусто/None → импортировать все товары сообщества.
    external_ids: Optional[list[str]] = Field(default=None, max_length=1000)


@router.get("/status")
async def vk_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _my_shop(current_user, db)
    integration = await vk_import_service.get_integration(db, shop.id)
    return {
        "configured": vk_client.configured(),   # приложение VK зарегистрировано?
        "connected": bool(integration and integration.access_token),
        "community_id": integration.community_id if integration else None,
        "community_name": integration.community_name if integration else None,
        "last_sync_at": integration.last_sync_at if integration else None,
    }


@router.get("/auth-url")
async def vk_auth_url(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    if not vk_client.configured():
        raise HTTPException(status_code=503, detail="Интеграция VK не настроена (VK_APP_ID/SECRET/REDIRECT_URI)")
    await _my_shop(current_user, db)  # ensure the seller has a shop up-front
    state = create_access_token(current_user.id)  # short-lived signed identity
    return {"url": vk_client.build_auth_url(state)}


@router.get("/callback")
async def vk_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = verify_token(state, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Недействительный state")
    user = (await db.execute(select(User).where(User.id == int(user_id)))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    shop = await _my_shop(user, db)

    try:
        token_data = await vk_client.exchange_code(code)
    except vk_client.VkApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    integration = await vk_import_service.get_integration(db, shop.id)
    if not integration:
        integration = ShopIntegration(shop_id=shop.id, provider="vk")
        db.add(integration)
    integration.access_token = token_data["access_token"]
    integration.external_user_id = str(token_data.get("user_id", ""))
    await db.commit()

    return RedirectResponse(_seller_cabinet_url("/import?vk=connected"))


@router.get("/communities")
async def vk_communities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _my_shop(current_user, db)
    integration = await vk_import_service.get_integration(db, shop.id)
    if not integration or not integration.access_token:
        raise HTTPException(status_code=400, detail="Сначала подключите VK")
    try:
        return await vk_client.get_admin_communities(integration.access_token)
    except vk_client.VkApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/preview")
async def vk_preview(
    payload: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _my_shop(current_user, db)
    integration = await vk_import_service.get_integration(db, shop.id)
    if not integration or not integration.access_token:
        raise HTTPException(status_code=400, detail="Сначала подключите VK")
    try:
        items = await vk_import_service.preview_items(integration.access_token, payload.community_id)
    except vk_client.VkApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"items": items, "count": len(items)}


@router.post("/import", status_code=202)
async def vk_import(
    payload: ImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    shop = await _my_shop(current_user, db)
    integration = await vk_import_service.get_integration(db, shop.id)
    if not integration or not integration.access_token:
        raise HTTPException(status_code=400, detail="Сначала подключите VK")

    # Remember the chosen community for future re-syncs.
    integration.community_id = str(payload.community_id)
    await db.commit()

    from app.tasks.tasks import import_vk_products
    task = import_vk_products.delay(
        shop.id, payload.community_id, payload.category_id, payload.external_ids
    )
    return {"task_id": task.id}


@router.get("/import/{task_id}")
async def vk_import_status(
    task_id: str,
    current_user: User = Depends(get_current_seller),
):
    from app.tasks.celery_app import celery_app
    res = celery_app.AsyncResult(task_id)
    out = {"state": res.state}
    if res.state == "SUCCESS":
        out["result"] = res.result
    elif res.state == "FAILURE":
        out["error"] = str(res.result)
    elif isinstance(res.info, dict):
        out["progress"] = res.info
    return out
