"""
Reviews endpoints: creation with moderation gating, seller replies, helpful votes.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models.models import (
    Order, OrderItem, OrderStatus, Product, Review, ReviewReply,
    ReviewStatus, ReviewVote, Shop, User,
)
from app.schemas.schemas import (
    ReviewCreate, ReviewOut, ReviewReplyCreate, ReviewReplyOut, ShopRatingSummary,
)
from app.services import rating_service
from app.services.settings_service import is_review_premoderation_enabled

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _to_review_out(review: Review, current_user_id: int | None) -> ReviewOut:
    out = ReviewOut.model_validate(review)
    if current_user_id is not None:
        out.voted_by_me = any(v.user_id == current_user_id for v in review.votes)
    return out


async def _recalculate_product_rating(product_id: int, db: AsyncSession) -> None:
    """Refresh product + owning-shop ratings from approved reviews."""
    await rating_service.recalculate_for_product(db, product_id)


@router.get("/product/{product_id}", response_model=dict)
async def get_product_reviews(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    verified_only: bool = Query(False),
):
    """Public listing: only approved reviews are visible here. Pass
    verified_only=true to restrict to verified-purchase reviews."""
    query = (
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.reply), selectinload(Review.votes), selectinload(Review.photos))
        .where(Review.product_id == product_id, Review.status == ReviewStatus.approved)
        .order_by(Review.helpful_count.desc(), Review.created_at.desc())
    )
    if verified_only:
        query = query.where(Review.is_verified_purchase.is_(True))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    reviews = result.scalars().all()
    return {
        "items": [_to_review_out(r, None) for r in reviews],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/shop/{shop_id}/summary", response_model=ShopRatingSummary)
async def get_shop_rating_summary(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Seller rating overview: average, total approved reviews, verified count,
    and the 1–5 star distribution (aggregated across the shop's products)."""
    shop = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return await rating_service.shop_rating_summary(db, shop_id)


@router.post("/product/{product_id}", response_model=ReviewOut, status_code=201)
async def create_review(
    product_id: int,
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a review. Only buyers who purchased and received (status=completed)
    the product may review it. The review enters 'pending' status if review
    premoderation is enabled (default), otherwise it's published immediately.
    """
    purchased = (await db.execute(
        select(OrderItem)
        .join(Order)
        .where(
            Order.buyer_id == current_user.id,
            OrderItem.product_id == product_id,
            Order.status == OrderStatus.completed,
        )
        .order_by(Order.created_at.desc())
    )).scalars().first()
    if not purchased:
        raise HTTPException(
            status_code=403,
            detail="You can only review products you have purchased and received",
        )

    existing = await db.execute(
        select(Review).where(
            Review.user_id == current_user.id,
            Review.product_id == product_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    premod = await is_review_premoderation_enabled(db)
    initial_status = ReviewStatus.pending if premod else ReviewStatus.approved

    review = Review(
        user_id=current_user.id,
        product_id=product_id,
        rating=payload.rating,
        text=payload.text,
        status=initial_status,
        # The review is backed by a completed order, so it's a verified purchase.
        is_verified_purchase=True,
        order_id=purchased.order_id,
    )
    db.add(review)
    await db.flush()

    # Attach media — photos first, then short videos (capped).
    from app.models.models import ReviewPhoto
    idx = 0
    for url in payload.photos[:8]:
        db.add(ReviewPhoto(review_id=review.id, url=url, media_type="image", sort_order=idx)); idx += 1
    for url in payload.videos[:3]:
        db.add(ReviewPhoto(review_id=review.id, url=url, media_type="video", sort_order=idx)); idx += 1

    if initial_status == ReviewStatus.approved:
        await rating_service.recalculate_for_product(db, product_id)

    await db.commit()
    await db.refresh(review)
    await db.refresh(review, ["user", "reply", "votes", "photos"])
    return _to_review_out(review, current_user.id)


@router.post("/upload-media")
async def upload_review_media(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """Upload a review photo or short video. Returns {url, media_type}."""
    from app.services.storage_service import save_public_media
    content = await file.read()
    try:
        url, media_type = await save_public_media(content, file.content_type or "", file.filename or "media")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"url": url, "media_type": media_type}


@router.get("/product/{product_id}/media")
async def product_review_media(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(24, ge=1, le=60),
):
    """Aggregated customer photos+videos for a product (approved reviews only) —
    powers the 'Фото и видео покупателей' gallery on the product page."""
    from app.models.models import ReviewPhoto
    rows = (await db.execute(
        select(ReviewPhoto)
        .join(Review, Review.id == ReviewPhoto.review_id)
        .where(Review.product_id == product_id, Review.status == ReviewStatus.approved)
        .order_by(ReviewPhoto.media_type.desc(), ReviewPhoto.id.desc())
        .limit(limit)
    )).scalars().all()
    return [{"id": m.id, "url": m.url, "media_type": m.media_type} for m in rows]


@router.get("/my", response_model=list[ReviewOut])
async def get_my_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current user's own reviews regardless of moderation status."""
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.reply), selectinload(Review.votes), selectinload(Review.photos))
        .where(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    return [_to_review_out(r, current_user.id) for r in reviews]


# ─── Helpful votes ("likes") ───────────────────────────────────────────────────

@router.post("/{review_id}/vote", status_code=200)
async def vote_helpful(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a review as helpful. Idempotent: voting again toggles the vote off."""
    result = await db.execute(select(Review).where(Review.id == review_id, Review.status == ReviewStatus.approved))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    existing = await db.execute(
        select(ReviewVote).where(ReviewVote.review_id == review_id, ReviewVote.user_id == current_user.id)
    )
    vote = existing.scalar_one_or_none()

    if vote:
        await db.delete(vote)
        review.helpful_count = max(0, review.helpful_count - 1)
        voted = False
    else:
        db.add(ReviewVote(review_id=review_id, user_id=current_user.id))
        review.helpful_count += 1
        voted = True

    await db.commit()
    return {"voted": voted, "helpful_count": review.helpful_count}


# ─── Seller replies ─────────────────────────────────────────────────────────────

@router.post("/{review_id}/reply", response_model=ReviewReplyOut, status_code=201)
async def create_or_update_reply(
    review_id: int,
    payload: ReviewReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """
    Seller responds to a review left on one of their products.
    One reply per review; calling again edits the existing reply.
    """
    result = await db.execute(
        select(Review).options(selectinload(Review.reply)).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Verify the current seller owns the product being reviewed
    shop_result = await db.execute(select(Shop).where(Shop.owner_id == current_user.id))
    shop = shop_result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=403, detail="You don't have a shop")

    product_result = await db.execute(
        select(Product).where(Product.id == review.product_id, Product.shop_id == shop.id)
    )
    if not product_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You can only reply to reviews on your own products")

    if review.reply:
        review.reply.text = payload.text
        reply = review.reply
    else:
        reply = ReviewReply(review_id=review_id, seller_id=current_user.id, text=payload.text)
        db.add(reply)

    await db.commit()
    await db.refresh(reply)
    return reply


@router.delete("/{review_id}/reply", status_code=204)
async def delete_reply(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(select(ReviewReply).where(ReviewReply.review_id == review_id))
    reply = result.scalar_one_or_none()
    if not reply or reply.seller_id != current_user.id:
        raise HTTPException(status_code=404, detail="Reply not found")
    await db.delete(reply)
    await db.commit()
