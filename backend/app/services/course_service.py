"""
Course-generator service: orchestrates the two-step pipeline that turns a
CourseGenerationRequest into a CourseOutline.

Pipeline:
  1. Research phase — reuses `agent_service.run_agent` with a course-specific
     system prompt. The agent calls `search_wikipedia` per planned lesson and
     emits plain-text research notes. We forward all streamed frames downstream
     and accumulate the assistant text.
  2. Assembly phase — one `ollama_service.chat_structured` call with the
     CourseOutline JSON Schema as Ollama's `format=` parameter. Returns a
     Pydantic-validated outline.
  3. Validation — server-side cross-reference check (prerequisite_ids,
     assesses_outcome_ids, hours-in-range). Errors set status=needs_review
     instead of rejecting outright.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.db.models import Course, CourseStatus, RagServer, Settings
from app.db.session import AsyncSessionLocal
from app.schemas.course import (
    AgeCategory,
    CourseGenerationRequest,
    CourseOutline,
)
from app.services.agent_service import AgentRunResult, run_agent
from app.services.ollama_service import ollama_service

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt loading + template substitution
# ---------------------------------------------------------------------------


_AGE_DESCRIPTIONS: Dict[AgeCategory, str] = {
    AgeCategory.PRIMARY: "primary school student (grade 1-3)",
    AgeCategory.ELEMENTARY: "elementary school student (grade 4-7)",
    AgeCategory.JUNIOR_HIGH: "junior high student (grade 8-9)",
    AgeCategory.SENIOR_HIGH: "senior high student (grade 10-12)",
    AgeCategory.COLLEGE: "college (non-US) / community college student",
    AgeCategory.BACHELORS: "undergraduate bachelor's-level student",
    AgeCategory.MASTERS: "master's-level student",
    AgeCategory.PHD: "doctoral / PhD-level student",
}


def _prompt_dir() -> Path:
    """Locate the prompts directory by walking up from this file."""
    # config holds title/memory prompt paths relative to backend/ — use the
    # title prompt's parent as the prompt dir to be robust to test envs.
    title_path = Path(app_settings.title_generation_prompt_file)
    if title_path.is_absolute() and title_path.parent.exists():
        return title_path.parent
    return Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _prompt_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Course prompt template missing: {path}")
    return path.read_text().strip()


def _render_prompt(template: str, request: CourseGenerationRequest) -> str:
    resources = (
        ", ".join(r.value for r in request.included_resources)
        if request.included_resources
        else "none specified"
    )
    return (
        template.replace("{topic}", request.topic)
        .replace("{age_description}", _AGE_DESCRIPTIONS[request.age_category])
        .replace("{age_category}", request.age_category.value)
        .replace("{current_expertise}", request.current_expertise.value)
        .replace("{target_expertise}", request.target_expertise.value)
        .replace("{hours_min}", str(request.hours_min))
        .replace("{hours_max}", str(request.hours_max))
        .replace("{included_resources}", resources)
        .replace(
            "{learner_context}",
            request.learner_context or "none provided",
        )
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_outline(
    outline: CourseOutline, request: CourseGenerationRequest
) -> List[Dict[str, str]]:
    """Server-side coherence check for a generated outline.

    Returns a list of `{path, msg}` dicts. Non-empty result sets the Course
    to `needs_review` rather than rejecting the generation.
    """
    errors: List[Dict[str, str]] = []

    outcome_ids: set[str] = {o.id for o in outline.course_outcomes}
    for module in outline.modules:
        outcome_ids |= {o.id for o in module.outcomes}

    seen_lesson_ids: set[str] = set()
    seen_module_ids: set[str] = set()

    for mi, module in enumerate(outline.modules):
        for li, lesson in enumerate(module.lessons):
            for pid in lesson.prerequisite_ids:
                if pid not in seen_lesson_ids and pid not in seen_module_ids:
                    errors.append(
                        {
                            "path": f"modules[{mi}].lessons[{li}].prerequisite_ids",
                            "msg": f"unknown prerequisite '{pid}'",
                        }
                    )
            for ai, assessment in enumerate(lesson.assessments):
                for oid in assessment.assesses_outcome_ids:
                    if oid not in outcome_ids:
                        errors.append(
                            {
                                "path": (
                                    f"modules[{mi}].lessons[{li}]."
                                    f"assessments[{ai}].assesses_outcome_ids"
                                ),
                                "msg": f"unknown outcome '{oid}'",
                            }
                        )
            seen_lesson_ids.add(lesson.id)
        seen_module_ids.add(module.id)

    # Coverage check: every declared outcome must be exercised by >=1 assessment.
    assessed_outcome_ids: set[str] = set()
    for module in outline.modules:
        for lesson in module.lessons:
            for assessment in lesson.assessments:
                assessed_outcome_ids.update(assessment.assesses_outcome_ids)

    for oid in sorted(outcome_ids - assessed_outcome_ids):
        errors.append(
            {
                "path": "course_outcomes/modules.outcomes",
                "msg": f"outcome '{oid}' is declared but never exercised by any assessment",
            }
        )

    total = sum(
        lesson.estimated_hours
        for module in outline.modules
        for lesson in module.lessons
    )
    if not (request.hours_min <= total <= request.hours_max):
        errors.append(
            {
                "path": "modules[*].lessons[*].estimated_hours",
                "msg": (
                    f"total {total:g}h not in "
                    f"[{request.hours_min}, {request.hours_max}]"
                ),
            }
        )

    return errors


# ---------------------------------------------------------------------------
# RAG context gate
# ---------------------------------------------------------------------------


def _has_rag_context(rag_server: Optional[RagServer], rag_top_k: Optional[int]) -> bool:
    """The agent loop reads (rag_server.url, rag_server.corpus_id, rag_top_k).

    Returns True iff all three are set. The Course's NOT NULL constraints
    make this practically redundant on the create path, but it's still useful
    on the generate path in case the RAG server got deleted out from under
    the course between creation and generation.
    """
    return bool(rag_server is not None and rag_top_k is not None and rag_top_k > 0)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def _run_research_phase(
    *,
    request: CourseGenerationRequest,
    rag_server: RagServer,
    rag_top_k: int,
    model: str,
    user_settings: Settings,
    effective_temperature: float,
    effective_num_ctx: int,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield research-phase frames AND a synthetic final frame
    `{"type": "_research_notes", "content": <str>}` for the orchestrator to
    consume. The underscore prefix signals "internal — do not forward to client".
    """
    system_prompt = _render_prompt(_load_prompt("course_research_agent.md"), request)
    initial_messages: List[Dict[str, Any]] = [
        {"role": "user", "content": "Research and plan the course."}
    ]
    options = {
        "temperature": effective_temperature,
        "num_ctx": effective_num_ctx,
    }
    result = AgentRunResult()

    async for frame in run_agent(
        model=model,
        initial_messages=initial_messages,
        options=options,
        rag_server=rag_server,
        rag_top_k=rag_top_k,
        result=result,
        is_disconnected=is_disconnected,
        max_iters=8,  # research benefits from a bit more headroom than chat agent
        system_prompt=system_prompt,
    ):
        yield frame
        if frame.get("type") == "error":
            return

    yield {"type": "_research_notes", "content": result.final_content}


async def generate_course(
    *,
    course_id: UUID,
    user_id: UUID,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Drive the two-step pipeline against a fresh DB session.

    Yields frames for the caller (the streaming endpoint) to serialize as
    NDJSON. The course row is mutated and committed inside this generator;
    we deliberately do NOT reuse the request's session because dependency
    cleanup may close it before the stream finishes (mirrors the chat
    agent's persistence pattern — see `_persist_assistant_message`).

    Internal frames (those whose `type` starts with `_`) are an internal
    coordination channel between phases and are filtered before yielding
    to the caller.
    """
    async with AsyncSessionLocal() as db:
        # Load the course + rag_server eagerly so the agent loop can read
        # rag_server.url / .corpus_id without lazy-loading on a closed session.
        course = (
            await db.execute(
                select(Course)
                .where(Course.id == course_id, Course.user_id == user_id)
                .options(selectinload(Course.rag_server))
            )
        ).scalar_one_or_none()
        if course is None:
            yield {"type": "error", "message": f"Course {course_id} not found"}
            yield {"type": "done", "status": CourseStatus.FAILED.value}
            return

        # Load the user's Settings inside this session too.
        user_settings = (
            await db.execute(select(Settings).where(Settings.user_id == user_id))
        ).scalar_one_or_none()
        if user_settings is None:
            yield {"type": "error", "message": "User settings missing"}
            yield {"type": "done", "status": CourseStatus.FAILED.value}
            return

        rag_server = course.rag_server
        rag_top_k = course.rag_top_k

        try:
            request = CourseGenerationRequest.model_validate(course.input)
        except ValidationError as exc:
            msg = f"Stored input failed validation: {exc.errors()}"
            course.status = CourseStatus.FAILED
            course.validation_errors = [{"path": "input", "msg": msg}]
            await db.commit()
            yield {"type": "error", "message": msg}
            yield {"type": "done", "status": course.status.value}
            return

        if not _has_rag_context(rag_server, rag_top_k):
            msg = (
                "Course has no usable RAG context (rag_server missing or "
                "rag_top_k unset). The RAG server may have been deleted; pick "
                "a different one from the course settings and retry."
            )
            course.status = CourseStatus.FAILED
            course.validation_errors = [{"path": "course.rag", "msg": msg}]
            await db.commit()
            yield {"type": "error", "message": msg}
            yield {"type": "done", "status": course.status.value}
            return

        # Status -> generating, persisted so the GET endpoint reflects in-flight state.
        course.status = CourseStatus.GENERATING
        course.validation_errors = None
        course.outline = None
        await db.commit()

        model = course.override_model or user_settings.default_model
        effective_temperature = (
            course.override_temperature
            if course.override_temperature is not None
            else user_settings.default_temperature
        )
        effective_num_ctx = (
            course.override_num_ctx
            if course.override_num_ctx is not None
            else user_settings.num_ctx
        )

        yield {"type": "phase", "name": "research"}

        research_notes = ""
        research_failed = False
        async for frame in _run_research_phase(
            request=request,
            rag_server=rag_server,
            rag_top_k=rag_top_k,
            model=model,
            user_settings=user_settings,
            effective_temperature=effective_temperature,
            effective_num_ctx=effective_num_ctx,
            is_disconnected=is_disconnected,
        ):
            ftype = frame.get("type", "")
            if ftype == "_research_notes":
                research_notes = frame.get("content", "")
                continue
            if ftype == "error":
                research_failed = True
            yield frame

        if research_failed:
            course.status = CourseStatus.FAILED
            await db.commit()
            yield {"type": "done", "status": course.status.value}
            return

        if not research_notes.strip():
            course.status = CourseStatus.FAILED
            course.validation_errors = [
                {"path": "phase-1", "msg": "research phase produced no notes"}
            ]
            await db.commit()
            yield {
                "type": "error",
                "message": "Research phase produced no notes; cannot assemble outline.",
            }
            yield {"type": "done", "status": course.status.value}
            return

        yield {"type": "phase", "name": "assembling"}

        assembly_system_prompt = _render_prompt(
            _load_prompt("course_assembly.md"), request
        )
        assembly_messages = [
            {"role": "system", "content": assembly_system_prompt},
            {
                "role": "user",
                "content": (
                    f"Research notes:\n\n{research_notes}\n\n"
                    "Produce the CourseOutline JSON now."
                ),
            },
        ]
        assembly_options = {
            # Lower temperature for structured output to stay closer to the schema.
            "temperature": 0.2,
            # Give the assembly call plenty of context for big research dumps.
            "num_ctx": max(effective_num_ctx, 8192),
        }

        try:
            raw_json = await ollama_service.chat_structured(
                model=model,
                messages=assembly_messages,
                json_schema=CourseOutline.model_json_schema(),
                options=assembly_options,
            )
        except Exception as exc:
            msg = f"Assembly call failed: {exc}"
            logger.error(msg)
            course.status = CourseStatus.FAILED
            course.validation_errors = [{"path": "phase-2.ollama", "msg": str(exc)}]
            await db.commit()
            yield {"type": "error", "message": msg}
            yield {"type": "done", "status": course.status.value}
            return

        try:
            outline = CourseOutline.model_validate_json(raw_json)
        except ValidationError as exc:
            msg = "Assembly output failed Pydantic validation."
            logger.error("%s Details: %s", msg, exc.errors()[:3])
            course.status = CourseStatus.FAILED
            course.validation_errors = [
                {"path": "phase-2.parse", "msg": str(exc.errors()[:5])}
            ]
            await db.commit()
            yield {"type": "error", "message": msg}
            yield {"type": "done", "status": course.status.value}
            return

        errors = validate_outline(outline, request)
        course.outline = outline.model_dump()
        course.validation_errors = errors or None
        course.model_used = model
        course.generated_at = datetime.now(timezone.utc)
        course.status = CourseStatus.NEEDS_REVIEW if errors else CourseStatus.COMPLETE
        await db.commit()

        yield {"type": "outline", "content": course.outline}
        if errors:
            yield {"type": "validation", "errors": errors}
        yield {"type": "done", "status": course.status.value}
