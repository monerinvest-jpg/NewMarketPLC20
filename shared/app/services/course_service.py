"""
Course/LMS helpers: access checks, curriculum assembly (with per-lesson gating
and progress), and lazy creation of the Course record for a course product.

Course access reuses the digital-goods Entitlement: buying a course-type product
grants access, exactly like a digital download.
"""
import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Course, CourseLesson, CourseModule, LessonProgress, LessonType, Product, User,
)
from app.schemas.schemas import CourseOut, LessonOut, ModuleOut
from app.services import entitlement_service


def _quiz_for_view(quiz_json: str, include_answers: bool) -> dict:
    """Parse stored quiz JSON for display. Buyers never receive the answer key."""
    try:
        data = json.loads(quiz_json) or {}
    except Exception:
        return {"pass_score": 70, "questions": []}
    questions = []
    for q in data.get("questions", []):
        item = {"q": q.get("q", ""), "options": q.get("options", [])}
        if include_answers:
            item["correct"] = q.get("correct", 0)
        questions.append(item)
    return {"pass_score": int(data.get("pass_score", 70)), "questions": questions}


def grade_quiz(quiz_json: Optional[str], answers: list[int]) -> tuple[int, bool, int, int]:
    """Grade submitted answers against the stored key.
    Returns (score_percent, passed, correct_count, total)."""
    try:
        data = json.loads(quiz_json or "{}") or {}
    except Exception:
        data = {}
    questions = data.get("questions", [])
    total = len(questions)
    if total == 0:
        return 0, False, 0, 0
    correct = 0
    for i, q in enumerate(questions):
        chosen = answers[i] if i < len(answers) else -1
        if chosen == q.get("correct", 0):
            correct += 1
    score = int(round(correct / total * 100))
    passed = score >= int(data.get("pass_score", 70))
    return score, passed, correct, total


async def get_course_for_product(db: AsyncSession, product_id: int) -> Optional[Course]:
    return (await db.execute(
        select(Course)
        .options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .where(Course.product_id == product_id)
    )).scalar_one_or_none()


async def ensure_course(db: AsyncSession, product: Product) -> Course:
    """Get (or lazily create) the Course record for a course-type product."""
    course = (await db.execute(
        select(Course).where(Course.product_id == product.id)
    )).scalar_one_or_none()
    if course is None:
        course = Course(product_id=product.id, shop_id=product.shop_id)
        db.add(course)
        await db.flush()
    return course


async def has_access(db: AsyncSession, user: Optional[User], product_id: int) -> bool:
    """True if the user owns the course (active entitlement)."""
    if user is None:
        return False
    ent = await entitlement_service.get_active_entitlement(db, user.id, product_id)
    return ent is not None


async def _completed_lesson_ids(db: AsyncSession, user_id: int, course_id: int) -> set[int]:
    rows = (await db.execute(
        select(LessonProgress.lesson_id).where(
            LessonProgress.user_id == user_id,
            LessonProgress.course_id == course_id,
            LessonProgress.completed == True,  # noqa: E712
        )
    )).scalars().all()
    return set(rows)


async def build_curriculum(
    db: AsyncSession, course: Course, product: Product, user: Optional[User],
    force_unlock: bool = False,
) -> CourseOut:
    """Assemble the full course view: modules/lessons with per-lesson access
    (entitled or preview) and the user's progress. Locked lessons never leak
    their text/file. `force_unlock` is for the owning seller's builder view."""
    enrolled = force_unlock or await has_access(db, user, course.product_id)
    completed_ids = await _completed_lesson_ids(db, user.id, course.id) if user else set()

    total_lessons = 0
    completed_lessons = 0
    modules_out: list[ModuleOut] = []
    for module in sorted(course.modules, key=lambda m: m.sort_order):
        lessons_out: list[LessonOut] = []
        for lesson in sorted(module.lessons, key=lambda l: l.sort_order):
            total_lessons += 1
            unlocked = enrolled or lesson.is_preview
            done = lesson.id in completed_ids
            if done:
                completed_lessons += 1
            quiz_payload = None
            if lesson.lesson_type == LessonType.quiz and lesson.quiz_json and unlocked:
                quiz_payload = _quiz_for_view(lesson.quiz_json, include_answers=force_unlock)
            lessons_out.append(LessonOut(
                id=lesson.id,
                title=lesson.title,
                lesson_type=lesson.lesson_type,
                duration_seconds=lesson.duration_seconds,
                is_preview=lesson.is_preview,
                sort_order=lesson.sort_order,
                has_file=bool(lesson.storage_key),
                hls_ready=bool(getattr(lesson, "hls_ready", False)),
                locked=not unlocked,
                completed=done,
                text_body=lesson.text_body if (unlocked and lesson.lesson_type == LessonType.text) else None,
                quiz=quiz_payload,
            ))
        modules_out.append(ModuleOut(
            id=module.id, title=module.title, sort_order=module.sort_order, lessons=lessons_out,
        ))

    pct = int(round(completed_lessons / total_lessons * 100)) if total_lessons else 0
    return CourseOut(
        id=course.id,
        product_id=course.product_id,
        shop_id=course.shop_id,
        title=product.title,
        slug=product.slug,
        level=course.level,
        language=course.language,
        has_intro_video=bool(course.intro_video_key),
        enrolled=enrolled,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,
        progress_percent=pct,
        modules=modules_out,
    )


async def course_progress_percent(db: AsyncSession, user_id: int, course_id: int) -> int:
    total = (await db.execute(
        select(func.count()).select_from(CourseLesson).where(CourseLesson.course_id == course_id)
    )).scalar_one()
    if not total:
        return 0
    done = len(await _completed_lesson_ids(db, user_id, course_id))
    return int(round(done / total * 100))
