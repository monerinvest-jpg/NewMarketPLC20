"""
Courses / built-in learning platform (LMS).

Public course detail + curriculum, the buyer's lesson playback (entitlement- or
preview-gated), progress tracking, and the seller's course builder. Course access
reuses the digital-goods Entitlement (buying a course-type product enrolls you).
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_seller, get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.models import (
    Course, CourseLesson, CourseModule, Entitlement, LessonProgress, LessonType,
    Product, ProductType, Shop, User,
)
from app.schemas.schemas import (
    CourseOut, CourseUpsert, LessonCreate, LessonOut, LessonUpdate, ModuleCreate, ModuleOut, ModuleUpdate,
)
from app.services import course_service, digital_storage_service

router = APIRouter(prefix="/courses", tags=["courses"])
learning_router = APIRouter(prefix="/learning", tags=["learning"])


# ─── seller ownership helpers ─────────────────────────────────────────────────

async def _seller_product(db: AsyncSession, user: User, product_id: int) -> Product:
    shop = (await db.execute(select(Shop).where(Shop.owner_id == user.id))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="У вас нет магазина")
    product = (await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if product.product_type != ProductType.course:
        raise HTTPException(status_code=400, detail="Товар не является курсом")
    return product


async def _seller_module(db: AsyncSession, user: User, product_id: int, module_id: int) -> CourseModule:
    await _seller_product(db, user, product_id)
    module = (await db.execute(
        select(CourseModule)
        .join(Course, Course.id == CourseModule.course_id)
        .where(CourseModule.id == module_id, Course.product_id == product_id)
    )).scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    return module


async def _seller_lesson(db: AsyncSession, user: User, product_id: int, lesson_id: int) -> CourseLesson:
    await _seller_product(db, user, product_id)
    lesson = (await db.execute(
        select(CourseLesson)
        .join(Course, Course.id == CourseLesson.course_id)
        .where(CourseLesson.id == lesson_id, Course.product_id == product_id)
    )).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


def _lesson_out(lesson: CourseLesson, unlocked: bool = True) -> LessonOut:
    return LessonOut(
        id=lesson.id, title=lesson.title, lesson_type=lesson.lesson_type,
        duration_seconds=lesson.duration_seconds, is_preview=lesson.is_preview,
        sort_order=lesson.sort_order, has_file=bool(lesson.storage_key),
        locked=not unlocked, completed=False,
        text_body=lesson.text_body if (unlocked and lesson.lesson_type == LessonType.text) else None,
    )


# ─── public / buyer: detail, playback, progress ───────────────────────────────

@router.get("/{product_id}", response_model=CourseOut)
async def get_course(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Course detail + curriculum. Preview lessons are open; the rest are locked
    until purchased."""
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product or product.product_type != ProductType.course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    course = await course_service.get_course_for_product(db, product_id)
    if not course:
        return CourseOut(
            id=0, product_id=product_id, shop_id=product.shop_id,
            title=product.title, slug=product.slug, modules=[],
            enrolled=await course_service.has_access(db, current_user, product_id),
        )
    return await course_service.build_curriculum(db, course, product, current_user)


@router.get("/{product_id}/lessons/{lesson_id}/content")
async def lesson_content(
    product_id: int,
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deliver a lesson's content. Requires an active entitlement to the course,
    unless the lesson is a free preview. Text is returned inline; video/PDF are
    streamed from private storage (S3 presigned redirect or a local stream).
    """
    lesson = (await db.execute(
        select(CourseLesson)
        .join(Course, Course.id == CourseLesson.course_id)
        .where(CourseLesson.id == lesson_id, Course.product_id == product_id)
    )).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    if not lesson.is_preview and not await course_service.has_access(db, current_user, product_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Курс не приобретён")

    if lesson.lesson_type == LessonType.text:
        return {"type": "text", "text_body": lesson.text_body or ""}

    if not lesson.storage_key:
        raise HTTPException(status_code=404, detail="Файл урока ещё не загружен")

    url = digital_storage_service.presigned_url(lesson.storage_key, lesson.title, expires=600)
    if url:
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    path = digital_storage_service.local_path(lesson.storage_key)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Файл недоступен")
    # FileResponse honours Range requests, so video can seek.
    return FileResponse(path, media_type=lesson.content_type or "application/octet-stream")


@router.post("/{product_id}/lessons/{lesson_id}/complete")
async def complete_lesson(
    product_id: int,
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not await course_service.has_access(db, current_user, product_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Курс не приобретён")
    lesson = (await db.execute(
        select(CourseLesson)
        .join(Course, Course.id == CourseLesson.course_id)
        .where(CourseLesson.id == lesson_id, Course.product_id == product_id)
    )).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    existing = (await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id
        )
    )).scalar_one_or_none()
    if not existing:
        db.add(LessonProgress(user_id=current_user.id, lesson_id=lesson_id, course_id=lesson.course_id))
        await db.commit()
    pct = await course_service.course_progress_percent(db, current_user.id, lesson.course_id)
    return {"completed": True, "progress_percent": pct}


# ─── buyer: my courses ────────────────────────────────────────────────────────

@learning_router.get("")
async def my_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Courses the buyer is enrolled in (owns), with overall progress."""
    from sqlalchemy.orm import selectinload
    ents = (await db.execute(
        select(Entitlement)
        .options(selectinload(Entitlement.product))
        .where(Entitlement.user_id == current_user.id, Entitlement.revoked == False)  # noqa: E712
        .order_by(Entitlement.granted_at.desc())
    )).scalars().all()
    out = []
    seen = set()
    for e in ents:
        p = e.product
        if not p or p.product_type != ProductType.course or p.id in seen:
            continue
        seen.add(p.id)
        course = await course_service.get_course_for_product(db, p.id)
        pct = await course_service.course_progress_percent(db, current_user.id, course.id) if course else 0
        out.append({
            "product_id": p.id, "title": p.title, "slug": p.slug,
            "progress_percent": pct, "course_id": course.id if course else None,
        })
    return out


# ─── seller: course builder ───────────────────────────────────────────────────

@router.get("/{product_id}/builder", response_model=CourseOut)
async def get_builder(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Full authoring view of the seller's own course (everything unlocked)."""
    product = await _seller_product(db, current_user, product_id)
    await course_service.ensure_course(db, product)
    await db.commit()
    course = await course_service.get_course_for_product(db, product_id)
    return await course_service.build_curriculum(db, course, product, current_user, force_unlock=True)


@router.put("/{product_id}/settings", response_model=CourseOut)
async def update_course_settings(
    product_id: int,
    payload: CourseUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    product = await _seller_product(db, current_user, product_id)
    course = await course_service.ensure_course(db, product)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    course = await course_service.get_course_for_product(db, product_id)
    return await course_service.build_curriculum(db, course, product, current_user, force_unlock=True)


@router.post("/{product_id}/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
async def add_module(
    product_id: int,
    payload: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    product = await _seller_product(db, current_user, product_id)
    course = await course_service.ensure_course(db, product)
    module = CourseModule(course_id=course.id, title=payload.title, sort_order=payload.sort_order)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return ModuleOut(id=module.id, title=module.title, sort_order=module.sort_order, lessons=[])


@router.put("/{product_id}/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    product_id: int,
    module_id: int,
    payload: ModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    module = await _seller_module(db, current_user, product_id, module_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    await db.commit()
    await db.refresh(module)
    return ModuleOut(id=module.id, title=module.title, sort_order=module.sort_order, lessons=[])


@router.delete("/{product_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    product_id: int,
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    module = await _seller_module(db, current_user, product_id, module_id)
    # clean up any stored lesson files
    lessons = (await db.execute(
        select(CourseLesson).where(CourseLesson.module_id == module_id)
    )).scalars().all()
    for lesson in lessons:
        if lesson.storage_key:
            digital_storage_service.delete_digital_asset(lesson.storage_key)
    await db.delete(module)
    await db.commit()


@router.post("/{product_id}/modules/{module_id}/lessons", response_model=LessonOut, status_code=status.HTTP_201_CREATED)
async def add_lesson(
    product_id: int,
    module_id: int,
    payload: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    module = await _seller_module(db, current_user, product_id, module_id)
    lesson = CourseLesson(
        module_id=module.id, course_id=module.course_id, title=payload.title,
        lesson_type=payload.lesson_type, text_body=payload.text_body,
        is_preview=payload.is_preview, sort_order=payload.sort_order,
        duration_seconds=payload.duration_seconds,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return _lesson_out(lesson, unlocked=True)


@router.put("/{product_id}/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    product_id: int,
    lesson_id: int,
    payload: LessonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    lesson = await _seller_lesson(db, current_user, product_id, lesson_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lesson, field, value)
    await db.commit()
    await db.refresh(lesson)
    return _lesson_out(lesson, unlocked=True)


@router.delete("/{product_id}/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    product_id: int,
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    lesson = await _seller_lesson(db, current_user, product_id, lesson_id)
    if lesson.storage_key:
        digital_storage_service.delete_digital_asset(lesson.storage_key)
    await db.delete(lesson)
    await db.commit()


@router.post("/{product_id}/lessons/{lesson_id}/file")
async def upload_lesson_file(
    product_id: int,
    lesson_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    """Upload the private video/PDF for a video/pdf lesson."""
    lesson = await _seller_lesson(db, current_user, product_id, lesson_id)
    if lesson.lesson_type == LessonType.text:
        raise HTTPException(status_code=400, detail="Текстовому уроку файл не нужен")
    content = await file.read()
    try:
        key, size = await digital_storage_service.save_digital_asset(
            content, file.content_type or "application/octet-stream", file.filename or "lesson",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if lesson.storage_key:
        digital_storage_service.delete_digital_asset(lesson.storage_key)
    lesson.storage_key = key
    lesson.content_type = file.content_type or "application/octet-stream"
    await db.commit()
    return {"ok": True, "size_bytes": size}
