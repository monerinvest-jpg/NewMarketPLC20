"""
Buyer's digital library: purchased digital products/courses and their secure
downloads. Every download is gated by an Entitlement (granted on payment).
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.models import DigitalAsset, Entitlement, Product, User
from app.schemas.schemas import EntitlementOut, EntitlementFileOut
from app.services import digital_storage_service, entitlement_service

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=list[EntitlementOut])
async def my_library(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All digital products/courses the buyer owns, with their downloadable files."""
    ents = (await db.execute(
        select(Entitlement)
        .options(selectinload(Entitlement.product).selectinload(Product.digital_assets))
        .where(Entitlement.user_id == current_user.id, Entitlement.revoked == False)  # noqa: E712
        .order_by(Entitlement.granted_at.desc())
    )).scalars().all()

    out: list[EntitlementOut] = []
    for e in ents:
        p = e.product
        assets = sorted(p.digital_assets, key=lambda a: (a.sort_order, a.id)) if p else []
        out.append(EntitlementOut(
            id=e.id,
            product_id=e.product_id,
            product_title=p.title if p else "",
            product_slug=p.slug if p else None,
            order_id=e.order_id,
            granted_at=e.granted_at,
            revoked=e.revoked,
            download_count=e.download_count,
            files=[
                EntitlementFileOut(
                    asset_id=a.id, file_name=a.file_name,
                    content_type=a.content_type, size_bytes=a.size_bytes,
                )
                for a in assets
            ],
        ))
    return out


@router.get("/{product_id}/files/{asset_id}")
async def download_file(
    product_id: int,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Securely deliver a digital file. Requires an active entitlement to the
    product. With object storage configured, redirects to a short-lived presigned
    URL; otherwise streams the privately stored file.
    """
    ent = await entitlement_service.get_active_entitlement(db, current_user.id, product_id)
    if not ent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому товару")

    asset = (await db.execute(
        select(DigitalAsset).where(DigitalAsset.id == asset_id, DigitalAsset.product_id == product_id)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Audit the access on the entitlement.
    ent.download_count += 1
    ent.last_downloaded_at = datetime.now(timezone.utc)
    await db.commit()

    # Prefer offloading bandwidth to object storage via a presigned URL.
    url = digital_storage_service.presigned_url(asset.storage_key, asset.file_name)
    if url:
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # Local private storage: stream through the app.
    path = digital_storage_service.local_path(asset.storage_key)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Файл недоступен")
    return FileResponse(path, filename=asset.file_name, media_type=asset.content_type)
