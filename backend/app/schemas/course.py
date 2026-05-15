"""
Pydantic schemas for the course generator.

Three families live here:

1. **Enums** — shared between request and output schemas.
2. **CourseGenerationRequest** — typed form input, persisted as JSONB on the
   Course row so we can regenerate from saved parameters.
3. **CourseOutline** (+ Module, Lesson, Outcome, Objective, Reading,
   Assessment) — the generated outline. Its `model_json_schema()` output is
   fed to Ollama's `format=` parameter during the assembly phase, so it must
   serialize to a clean JSON Schema.
4. **API schemas** — `CourseCreate`, `CourseUpdate`, `CourseRegenerateRequest`,
   `CourseResponse`, `CourseListItem`.
"""

import enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExpertiseLevel(str, enum.Enum):
    """Ordered expertise progression. Order matters: target >= current."""

    NONE = "none"
    NOVICE = "novice"
    COMPETENT = "competent"
    PROFICIENT = "proficient"
    EXPERT = "expert"


_EXPERTISE_ORDER = [
    ExpertiseLevel.NONE,
    ExpertiseLevel.NOVICE,
    ExpertiseLevel.COMPETENT,
    ExpertiseLevel.PROFICIENT,
    ExpertiseLevel.EXPERT,
]


class AgeCategory(str, enum.Enum):
    """Audience age category. Drives vocabulary and example complexity."""

    PRIMARY = "primary"  # grade 1-3
    ELEMENTARY = "elementary"  # grade 4-7
    JUNIOR_HIGH = "junior_high"  # grade 8-9
    SENIOR_HIGH = "senior_high"  # grade 10-12
    COLLEGE = "college"  # non-US college / community college level
    BACHELORS = "bachelors"
    MASTERS = "masters"
    PHD = "phd"


class ResourceType(str, enum.Enum):
    """Types of learning resources the course can include."""

    READINGS = "readings"
    PRACTICE_QUESTIONS = "practice_questions"
    QUIZZES = "quizzes"
    PROJECTS = "projects"


class BloomLevel(str, enum.Enum):
    """Bloom's taxonomy cognitive levels, lowest to highest."""

    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class AssessmentType(str, enum.Enum):
    """Assessment formats the LLM may emit per lesson."""

    QUIZ = "quiz"
    PRACTICE_QUESTION = "practice_question"
    PROJECT = "project"
    REFLECTION = "reflection"


class CourseStatus(str, enum.Enum):
    """Mirror of the DB-side CourseStatus enum, for API responses."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Input — CourseGenerationRequest
# ---------------------------------------------------------------------------


class CourseGenerationRequest(BaseModel):
    """The form payload that drives generation. Persisted as JSONB on Course.input."""

    topic: str = Field(..., min_length=2, max_length=200)
    current_expertise: ExpertiseLevel
    target_expertise: ExpertiseLevel
    age_category: AgeCategory
    hours_min: int = Field(..., ge=1, le=500)
    hours_max: int = Field(..., ge=1, le=500)
    included_resources: List[ResourceType] = Field(default_factory=list)
    learner_context: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("hours_max")
    @classmethod
    def _hours_max_gte_min(cls, v: int, info) -> int:
        hours_min = info.data.get("hours_min")
        if hours_min is not None and v < hours_min:
            raise ValueError("hours_max must be >= hours_min")
        return v

    @field_validator("target_expertise")
    @classmethod
    def _target_gte_current(cls, v: ExpertiseLevel, info) -> ExpertiseLevel:
        current = info.data.get("current_expertise")
        if current is not None:
            if _EXPERTISE_ORDER.index(v) < _EXPERTISE_ORDER.index(current):
                raise ValueError("target_expertise must be >= current_expertise")
        return v


# ---------------------------------------------------------------------------
# Output — CourseOutline + nested types
#
# `extra="forbid"` is set on every node so the JSON Schema fed to Ollama's
# format= mode rejects spurious fields. Every node carries an `id` slug
# (e.g. `mod-1`, `les-1-1`, `obj-1-1-1`) — IDs are how prerequisite and
# outcome cross-references resolve in validate_outline().
# ---------------------------------------------------------------------------


class Outcome(BaseModel):
    """Course-level or module-level outcome. Bloom's-tagged."""

    id: str = Field(..., description="Stable slug (e.g. 'out-c-1' or 'out-m-1-1').")
    text: str = Field(..., min_length=1)
    bloom_level: BloomLevel

    model_config = {"extra": "forbid"}


class Objective(BaseModel):
    """Lesson-level learning objective. Bloom's-tagged action verb."""

    id: str = Field(..., description="Stable slug (e.g. 'obj-1-1-1').")
    text: str = Field(..., min_length=1)
    bloom_level: BloomLevel

    model_config = {"extra": "forbid"}


class Reading(BaseModel):
    """A cited Wikipedia article (or other corpus document)."""

    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    snippet: Optional[str] = None

    model_config = {"extra": "forbid"}


class Assessment(BaseModel):
    """An assessment item that exercises one or more outcomes."""

    id: str = Field(..., description="Stable slug (e.g. 'asm-1-1-1').")
    type: AssessmentType
    prompt: str = Field(..., min_length=1)
    assesses_outcome_ids: List[str] = Field(
        ...,
        min_length=1,
        description="IDs of outcomes (course-level or module-level) this assessment exercises.",
    )

    model_config = {"extra": "forbid"}


class Lesson(BaseModel):
    """A single lesson within a module."""

    id: str = Field(..., description="Stable slug (e.g. 'les-1-1').")
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    estimated_hours: float = Field(..., gt=0)
    objectives: List[Objective] = Field(..., min_length=1)
    prerequisite_ids: List[str] = Field(
        default_factory=list,
        description="IDs of lessons or modules declared earlier in the outline.",
    )
    readings: List[Reading] = Field(default_factory=list)
    assessments: List[Assessment] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class Module(BaseModel):
    """A module groups related lessons under a shared set of outcomes."""

    id: str = Field(..., description="Stable slug (e.g. 'mod-1').")
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    estimated_hours: float = Field(..., gt=0)
    outcomes: List[Outcome] = Field(..., min_length=1)
    lessons: List[Lesson] = Field(..., min_length=1)

    model_config = {"extra": "forbid"}


class CourseOutline(BaseModel):
    """Top-level generated outline. Persisted to Course.outline as JSONB."""

    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    total_hours: float = Field(..., gt=0)
    course_outcomes: List[Outcome] = Field(..., min_length=1)
    modules: List[Module] = Field(..., min_length=1)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------


class CourseCreate(BaseModel):
    """Payload for POST /api/v1/courses."""

    project_id: UUID
    input: CourseGenerationRequest


class CourseUpdate(BaseModel):
    """Payload for PATCH /api/v1/courses/{id}. v1 only supports title edits."""

    title: Optional[str] = Field(None, min_length=1, max_length=256)


class CourseRegenerateRequest(BaseModel):
    """Optional payload for POST /api/v1/courses/{id}/regenerate.

    When `input` is present it overwrites the persisted CourseGenerationRequest
    on the row before regeneration kicks off.
    """

    input: Optional[CourseGenerationRequest] = None


class ValidationErrorEntry(BaseModel):
    """Shape of a single entry in Course.validation_errors."""

    path: str
    msg: str


class CourseResponse(BaseModel):
    """Schema for GET /api/v1/courses/{id} and POST /courses returns."""

    id: UUID
    user_id: UUID
    project_id: UUID
    title: str
    status: CourseStatus
    input: CourseGenerationRequest
    outline: Optional[CourseOutline] = None
    validation_errors: Optional[List[ValidationErrorEntry]] = None
    model_used: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    generated_at: Optional[datetime] = None

    # `model_used` would otherwise trigger a "protected namespace" warning
    # because Pydantic reserves `model_*` for its own attributes.
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class CourseListItem(BaseModel):
    """Lightweight projection for the courses list view."""

    id: UUID
    title: str
    project_id: UUID
    status: CourseStatus
    total_hours: Optional[float] = Field(
        None, description="Derived from outline.total_hours; null until generated."
    )
    topic: str = Field(..., description="Derived from input.topic for list display.")
    created_at: datetime
    updated_at: datetime
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
