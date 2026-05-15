"""
API endpoints for the course generator.

Routes (all under `/api/v1/courses`):
- POST /                 — create a Course (status=pending), persist input
- POST /{id}/generate    — drive the two-step pipeline, streaming NDJSON
- POST /{id}/regenerate  — reset state and re-drive generation
- GET  /                 — list user's courses (lightweight projection)
- GET  /{id}             — full course incl. outline
- PATCH /{id}            — update title
- DELETE /{id}           — hard delete

Generation streams use the same `application/x-ndjson` transport as the chat
agent endpoint. Frame types:
  {"type":"phase","name":"research"|"assembling"}
  {"type":"chunk","content":"..."}
  {"type":"tool_call","id":"...","name":"...","input":{...}}
  {"type":"tool_result","id":"...","ok":bool,"summary"|"error":"..."}
  {"type":"outline","content":{...CourseOutline...}}
  {"type":"validation","errors":[{"path","msg"},...]}
  {"type":"done","status":"complete|needs_review|failed"}
  {"type":"error","message":"..."}
"""

import json
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.db.models import Course, CourseStatus, RagServer, User
from app.db.models import Settings as UserSettings
from app.schemas.course import (
    CourseCreate,
    CourseListItem,
    CourseRegenerateRequest,
    CourseResponse,
    CourseUpdate,
)
from app.services.course_service import generate_course

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ndjson(payload: dict) -> bytes:
    """Encode one NDJSON line (single JSON object + newline)."""
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


async def _load_user_settings(db: AsyncSession, user_id: UUID) -> UserSettings:
    """Fetch the user's Settings row (seeded on first boot)."""
    row = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User settings row missing; lifespan seed did not run.",
        )
    return row


async def _load_course_or_404(
    db: AsyncSession, course_id: UUID, user_id: UUID
) -> Course:
    """Load a Course for the current user, eager-loading rag_server.

    Cross-user access returns 404 (not 403) to avoid leaking existence.
    """
    result = await db.execute(
        select(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .options(selectinload(Course.rag_server))
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )
    return course


async def _validate_rag_server_owned(
    db: AsyncSession, user: User, rag_server_id: UUID
) -> None:
    """Raise 422 if the referenced RAG server is missing or owned by another user.

    Mirrors `_validate_rag_server_owned` in endpoints/projects.py.
    """
    server = (
        await db.execute(
            select(RagServer).where(
                RagServer.id == rag_server_id, RagServer.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rag_server_id does not refer to a RAG server you own.",
        )


def _total_hours_from_outline(outline: dict | None) -> float | None:
    if not outline:
        return None
    try:
        return float(outline.get("total_hours")) if outline.get("total_hours") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course(
    body: CourseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseResponse:
    """Create a Course row in `status=pending`. Generation does not auto-fire.

    The course is bound to a RAG server (must be owned by the current user)
    and a top_k. It does not depend on a Project — courses are standalone.
    """
    await _validate_rag_server_owned(db, current_user, body.rag_server_id)

    course = Course(
        user_id=current_user.id,
        rag_server_id=body.rag_server_id,
        rag_top_k=body.rag_top_k,
        title=body.input.topic[:256],
        status=CourseStatus.PENDING,
        input=body.input.model_dump(mode="json"),
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return CourseResponse.model_validate(course)


@router.get("", response_model=list[CourseListItem])
async def list_courses(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseListItem]:
    """List the current user's courses, newest first."""
    rows = (
        (
            await db.execute(
                select(Course)
                .where(Course.user_id == current_user.id)
                .order_by(Course.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    items: list[CourseListItem] = []
    for c in rows:
        topic = ""
        if isinstance(c.input, dict):
            topic = str(c.input.get("topic", "")) or c.title
        items.append(
            CourseListItem(
                id=c.id,
                title=c.title,
                rag_server_id=c.rag_server_id,
                rag_top_k=c.rag_top_k,
                status=CourseStatus(
                    c.status.value if hasattr(c.status, "value") else c.status
                ),
                total_hours=_total_hours_from_outline(c.outline),
                topic=topic,
                created_at=c.created_at,
                updated_at=c.updated_at,
                generated_at=c.generated_at,
            )
        )
    return items


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseResponse:
    course = await _load_course_or_404(db, course_id, current_user.id)
    return CourseResponse.model_validate(course)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: UUID,
    body: CourseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseResponse:
    """Edit title and/or repoint the course at a different RAG server / top_k."""
    course = await _load_course_or_404(db, course_id, current_user.id)
    if body.rag_server_id is not None:
        await _validate_rag_server_owned(db, current_user, body.rag_server_id)
        course.rag_server_id = body.rag_server_id
    if body.rag_top_k is not None:
        course.rag_top_k = body.rag_top_k
    if body.title is not None:
        course.title = body.title
    await db.commit()
    await db.refresh(course)
    return CourseResponse.model_validate(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    course = await _load_course_or_404(db, course_id, current_user.id)
    await db.delete(course)
    await db.commit()


# ---------------------------------------------------------------------------
# Generation endpoints (streaming NDJSON)
# ---------------------------------------------------------------------------


async def _stream_generate(
    course_id: UUID,
    user_id: UUID,
    request: Request,
) -> AsyncGenerator[bytes, None]:
    """Drive the pipeline and serialize each frame as NDJSON.

    The course_service opens its own DB session because the request's session
    is closed when dependency cleanup runs (the streaming response may
    outlive the endpoint's return). See messages.py:_persist_assistant_message
    for the same pattern.
    """
    try:
        async for frame in generate_course(
            course_id=course_id,
            user_id=user_id,
            is_disconnected=request.is_disconnected,
        ):
            yield _ndjson(frame)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Course generation stream crashed: %s", exc)
        try:
            yield _ndjson({"type": "error", "message": f"Generation crashed: {exc}"})
            yield _ndjson({"type": "done", "status": CourseStatus.FAILED.value})
        except Exception:
            pass


@router.post("/{course_id}/generate")
async def generate(
    course_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Run the two-step pipeline against an existing Course. Streams NDJSON."""
    course = await _load_course_or_404(db, course_id, current_user.id)
    if course.rag_server is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Course has no RAG server. Pick one in the course settings, "
                "then retry."
            ),
        )
    # Surface a clear 500 here if the user's Settings row is missing, rather
    # than failing later inside the streaming generator.
    await _load_user_settings(db, current_user.id)
    return StreamingResponse(
        _stream_generate(course.id, current_user.id, request),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{course_id}/regenerate")
async def regenerate(
    course_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: CourseRegenerateRequest | None = None,
) -> StreamingResponse:
    """Optionally update the saved input, then re-run generation.

    Same streaming response as `/generate`. Course id is preserved.
    """
    course = await _load_course_or_404(db, course_id, current_user.id)

    if body is not None and body.input is not None:
        course.input = body.input.model_dump(mode="json")
        course.title = body.input.topic[:256]

    course.outline = None
    course.validation_errors = None
    course.generated_at = None
    course.status = CourseStatus.PENDING
    await db.commit()
    await db.refresh(course)

    if course.rag_server is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Course has no RAG server. Pick one in the course settings, "
                "then retry."
            ),
        )

    await _load_user_settings(db, current_user.id)
    return StreamingResponse(
        _stream_generate(course.id, current_user.id, request),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
