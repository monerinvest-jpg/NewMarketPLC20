"""
Seller Academy — platform-authored education for sellers. Admins manage courses
and lessons; sellers read them and track per-lesson completion. Built on the LMS
pattern (course → lessons → progress), decoupled from sellable products.

Routers:
  * admin_router  (/admin/academy)  — CRUD, included in the platform service
  * seller_router (/seller/academy) — read + progress, included in sellers service
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_moderator_or_admin, get_current_seller
from app.core.database import get_db
from app.models.models import AcademyCourse, AcademyLesson, AcademyProgress, User

admin_router = APIRouter(prefix="/admin/academy", tags=["academy-admin"])
seller_router = APIRouter(prefix="/seller/academy", tags=["academy-seller"])


def _course_dict(c: AcademyCourse, lesson_count: int | None = None) -> dict:
    d = {
        "id": c.id, "title": c.title, "description": c.description, "cover_url": c.cover_url,
        "level": c.level, "sort_order": c.sort_order, "is_published": c.is_published,
    }
    if lesson_count is not None:
        d["lesson_count"] = lesson_count
    return d


def _lesson_dict(l: AcademyLesson) -> dict:
    return {
        "id": l.id, "course_id": l.course_id, "title": l.title,
        "content_type": l.content_type, "body": l.body, "video_url": l.video_url,
        "sort_order": l.sort_order,
    }


# ─── Admin: course CRUD ─────────────────────────────────────────────────────────

@admin_router.get("/courses")
async def admin_list_courses(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    rows = (await db.execute(select(AcademyCourse).order_by(AcademyCourse.sort_order, AcademyCourse.id))).scalars().all()
    counts = dict((await db.execute(
        select(AcademyLesson.course_id, func.count(AcademyLesson.id)).group_by(AcademyLesson.course_id)
    )).all())
    return [_course_dict(c, counts.get(c.id, 0)) for c in rows]


@admin_router.post("/courses", status_code=201)
async def admin_create_course(payload: dict, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="Укажите название")
    c = AcademyCourse(
        title=payload["title"], description=payload.get("description"), cover_url=payload.get("cover_url"),
        level=payload.get("level", "beginner"), sort_order=int(payload.get("sort_order", 0)),
        is_published=bool(payload.get("is_published", False)),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return _course_dict(c, 0)


@admin_router.put("/courses/{course_id}")
async def admin_update_course(course_id: int, payload: dict, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    c = await db.get(AcademyCourse, course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Курс не найден")
    for f in ("title", "description", "cover_url", "level"):
        if f in payload:
            setattr(c, f, payload[f])
    if "sort_order" in payload:
        c.sort_order = int(payload["sort_order"])
    if "is_published" in payload:
        c.is_published = bool(payload["is_published"])
    await db.commit()
    return _course_dict(c)


@admin_router.delete("/courses/{course_id}", status_code=204)
async def admin_delete_course(course_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    c = await db.get(AcademyCourse, course_id)
    if c:
        await db.delete(c)
        await db.commit()


@admin_router.get("/courses/{course_id}/lessons")
async def admin_list_lessons(course_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    rows = (await db.execute(
        select(AcademyLesson).where(AcademyLesson.course_id == course_id).order_by(AcademyLesson.sort_order, AcademyLesson.id)
    )).scalars().all()
    return [_lesson_dict(l) for l in rows]


@admin_router.post("/courses/{course_id}/lessons", status_code=201)
async def admin_add_lesson(course_id: int, payload: dict, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    if not await db.get(AcademyCourse, course_id):
        raise HTTPException(status_code=404, detail="Курс не найден")
    l = AcademyLesson(
        course_id=course_id, title=payload.get("title", "Урок"),
        content_type=payload.get("content_type", "text"), body=payload.get("body"),
        video_url=payload.get("video_url"), sort_order=int(payload.get("sort_order", 0)),
    )
    db.add(l)
    await db.commit()
    await db.refresh(l)
    return _lesson_dict(l)


@admin_router.put("/lessons/{lesson_id}")
async def admin_update_lesson(lesson_id: int, payload: dict, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    l = await db.get(AcademyLesson, lesson_id)
    if not l:
        raise HTTPException(status_code=404, detail="Урок не найден")
    for f in ("title", "content_type", "body", "video_url"):
        if f in payload:
            setattr(l, f, payload[f])
    if "sort_order" in payload:
        l.sort_order = int(payload["sort_order"])
    await db.commit()
    return _lesson_dict(l)


@admin_router.delete("/lessons/{lesson_id}", status_code=204)
async def admin_delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_moderator_or_admin)):
    l = await db.get(AcademyLesson, lesson_id)
    if l:
        await db.delete(l)
        await db.commit()


# ─── Seller: read + progress ────────────────────────────────────────────────────

@seller_router.get("/courses")
async def seller_list_courses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    """Published courses with the seller's completion %."""
    courses = (await db.execute(
        select(AcademyCourse).where(AcademyCourse.is_published == True).order_by(AcademyCourse.sort_order, AcademyCourse.id)  # noqa: E712
    )).scalars().all()
    counts = dict((await db.execute(
        select(AcademyLesson.course_id, func.count(AcademyLesson.id)).group_by(AcademyLesson.course_id)
    )).all())
    # completed lessons by this user, grouped by course
    done_rows = (await db.execute(
        select(AcademyLesson.course_id, func.count(AcademyProgress.id))
        .join(AcademyProgress, AcademyProgress.lesson_id == AcademyLesson.id)
        .where(AcademyProgress.user_id == current_user.id)
        .group_by(AcademyLesson.course_id)
    )).all()
    done = dict(done_rows)
    out = []
    for c in courses:
        total = counts.get(c.id, 0)
        completed = done.get(c.id, 0)
        out.append({**_course_dict(c, total), "completed": completed,
                    "progress_percent": round(completed / total * 100) if total else 0})
    return out


@seller_router.get("/courses/{course_id}")
async def seller_get_course(course_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    c = (await db.execute(
        select(AcademyCourse).options(selectinload(AcademyCourse.lessons)).where(AcademyCourse.id == course_id)
    )).scalar_one_or_none()
    if not c or not c.is_published:
        raise HTTPException(status_code=404, detail="Курс не найден")
    completed_ids = set((await db.execute(
        select(AcademyProgress.lesson_id)
        .join(AcademyLesson, AcademyLesson.id == AcademyProgress.lesson_id)
        .where(AcademyProgress.user_id == current_user.id, AcademyLesson.course_id == course_id)
    )).scalars().all())
    return {
        **_course_dict(c, len(c.lessons)),
        "lessons": [{**_lesson_dict(l), "completed": l.id in completed_ids} for l in c.lessons],
    }


@seller_router.post("/lessons/{lesson_id}/complete")
async def seller_complete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_seller)):
    lesson = await db.get(AcademyLesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    exists = (await db.execute(
        select(AcademyProgress.id).where(
            AcademyProgress.user_id == current_user.id, AcademyProgress.lesson_id == lesson_id)
    )).scalar_one_or_none()
    if not exists:
        db.add(AcademyProgress(user_id=current_user.id, lesson_id=lesson_id))
        await db.commit()
    return {"ok": True}
