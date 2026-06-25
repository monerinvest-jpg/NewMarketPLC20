"""
Block 1 endpoints: product variants, attributes (filterable), and Q&A.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_seller, get_current_user, get_current_moderator_or_admin
from app.core.database import get_db
from app.models.models import (
    Attribute, NotificationType, Product, ProductAttributeValue,
    ProductQuestion, ProductVariant, Shop, User,
)
from app.schemas.schemas import (
    AttributeCreate, AttributeOut, ProductAnswerCreate,
    ProductAttributeValueIn, ProductAttributeValueOut,
    ProductQuestionCreate, ProductQuestionOut,
    ProductVariantCreate, ProductVariantOut,
)
from app.services.notification_service import notify

router = APIRouter(tags=["catalog-extra"])


async def _verify_product_owner(product_id: int, user: User, db: AsyncSession) -> Product:
    result = await db.execute(
        select(Product).join(Shop, Product.shop_id == Shop.id)
        .where(Product.id == product_id, Shop.owner_id == user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=403, detail="Это не ваш товар")
    return product


# ─── Variants ───────────────────────────────────────────────────────────────────

@router.get("/products/{product_id}/variants", response_model=list[ProductVariantOut])
async def list_variants(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id, ProductVariant.is_active == True)  # noqa: E712
        .order_by(ProductVariant.sort_order)
    )
    return result.scalars().all()


@router.post("/products/{product_id}/variants", response_model=ProductVariantOut, status_code=201)
async def create_variant(
    product_id: int,
    payload: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    await _verify_product_owner(product_id, current_user, db)
    variant = ProductVariant(product_id=product_id, **payload.model_dump())
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.put("/variants/{variant_id}", response_model=ProductVariantOut)
async def update_variant(
    variant_id: int,
    payload: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Вариант не найден")
    await _verify_product_owner(variant.product_id, current_user, db)
    for field, value in payload.model_dump().items():
        setattr(variant, field, value)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.delete("/variants/{variant_id}", status_code=204)
async def delete_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Вариант не найден")
    await _verify_product_owner(variant.product_id, current_user, db)
    await db.delete(variant)
    await db.commit()


# ─── Attributes (admin-managed definitions) ──────────────────────────────────────

@router.get("/attributes", response_model=list[AttributeOut])
async def list_attributes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Attribute).order_by(Attribute.sort_order))
    return result.scalars().all()


@router.post("/attributes", response_model=AttributeOut, status_code=201)
async def create_attribute(
    payload: AttributeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    attr = Attribute(**payload.model_dump())
    db.add(attr)
    await db.commit()
    await db.refresh(attr)
    return attr


@router.delete("/attributes/{attribute_id}", status_code=204)
async def delete_attribute(
    attribute_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_moderator_or_admin),
):
    result = await db.execute(select(Attribute).where(Attribute.id == attribute_id))
    attr = result.scalar_one_or_none()
    if not attr:
        raise HTTPException(status_code=404, detail="Атрибут не найден")
    await db.delete(attr)
    await db.commit()


# ─── Product attribute values (seller sets them on their products) ───────────────

@router.get("/products/{product_id}/attributes", response_model=list[ProductAttributeValueOut])
async def get_product_attributes(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductAttributeValue)
        .options(selectinload(ProductAttributeValue.attribute))
        .where(ProductAttributeValue.product_id == product_id)
    )
    return result.scalars().all()


@router.put("/products/{product_id}/attributes", response_model=list[ProductAttributeValueOut])
async def set_product_attributes(
    product_id: int,
    values: list[ProductAttributeValueIn],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Replace the full set of attribute values for a product."""
    await _verify_product_owner(product_id, current_user, db)
    # Clear existing then set new
    existing = await db.execute(
        select(ProductAttributeValue).where(ProductAttributeValue.product_id == product_id)
    )
    for v in existing.scalars().all():
        await db.delete(v)
    for item in values:
        db.add(ProductAttributeValue(
            product_id=product_id, attribute_id=item.attribute_id, value=item.value
        ))
    await db.commit()
    result = await db.execute(
        select(ProductAttributeValue)
        .options(selectinload(ProductAttributeValue.attribute))
        .where(ProductAttributeValue.product_id == product_id)
    )
    return result.scalars().all()


# ─── Product Q&A ─────────────────────────────────────────────────────────────────

@router.get("/products/{product_id}/questions", response_model=list[ProductQuestionOut])
async def list_questions(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductQuestion)
        .options(selectinload(ProductQuestion.user))
        .where(ProductQuestion.product_id == product_id)
        .order_by(ProductQuestion.created_at.desc())
    )
    return result.scalars().all()


@router.post("/products/{product_id}/questions", response_model=ProductQuestionOut, status_code=201)
async def ask_question(
    product_id: int,
    payload: ProductQuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prod_result = await db.execute(select(Product).where(Product.id == product_id))
    product = prod_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    question = ProductQuestion(product_id=product_id, user_id=current_user.id, question=payload.question)
    db.add(question)
    await db.flush()

    # Notify the shop owner about the new question
    shop_result = await db.execute(select(Shop).where(Shop.id == product.shop_id))
    shop = shop_result.scalar_one_or_none()
    if shop:
        await notify(
            db, shop.owner_id, NotificationType.question_answered,
            title="Новый вопрос о товаре",
            body=payload.question[:120],
            link=f"/products/{product_id}",
        )

    await db.commit()
    await db.refresh(question, ["user"])
    return question


@router.post("/questions/{question_id}/answer", response_model=ProductQuestionOut)
async def answer_question(
    question_id: int,
    payload: ProductAnswerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    result = await db.execute(
        select(ProductQuestion)
        .options(selectinload(ProductQuestion.user), selectinload(ProductQuestion.product))
        .where(ProductQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    await _verify_product_owner(question.product_id, current_user, db)

    question.answer = payload.answer
    question.answered_by_id = current_user.id
    question.answered_at = datetime.now(timezone.utc)
    await db.flush()

    # Notify the asker that their question was answered
    await notify(
        db, question.user_id, NotificationType.question_answered,
        title="Ответ на ваш вопрос",
        body=payload.answer[:120],
        link=f"/products/{question.product_id}",
    )

    await db.commit()
    await db.refresh(question, ["user"])
    return question
