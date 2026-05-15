# Course Generator — Implementation Plan

**Target executor:** Sonnet 4.6 agent
**Estimated scope:** ~11 sequential phases, each independently verifiable
**Status:** Approved design; ready to implement

## 0. Context

This feature lets a user generate a structured educational **course outline** for a topic, grounded by an external Wikipedia/RAG corpus that's already configured per-project in this repo. The user fills a form (topic, audience age, current → target expertise, target hours, included resources) and the system returns a Pydantic-validated `CourseOutline` containing modules, lessons, learning objectives (Bloom's-tagged), prerequisites, assessments, and cited Wikipedia readings.

**Why in this repo (not a separate project):** It reuses the existing agent infrastructure (`agent_service.run_agent`), the existing RAG-backed `search_wikipedia` tool, the Project → RAG-corpus relationship, the streaming NDJSON pattern, and the design system. The app remains single-user (Phase 7 auth stays deferred).

### 0.1 Locked design decisions (do not re-litigate)

| Axis | Decision |
| --- | --- |
| Scope (v1) | One-shot outline generation; no ongoing tutor |
| Audience | Single-user; Phase 7 auth stays deferred (continue using `get_current_user` → default user) |
| Data model | `Course` belongs to a `Project` (FK) so it inherits the project's RAG config; top-level at UX level |
| Wikipedia role | Cited reading list only. **No new tools.** Existing `search_wikipedia` (which queries the project's RAG server) is reused as-is |
| Pedagogical framework | Backward design + Bloom's taxonomy |
| Schema depth | Standard (title, summary, objectives, hours, prerequisites, readings, assessments) |
| Agent topology | **Two-step pipeline**: (1) existing agent loop for research with `search_wikipedia`, (2) one `chat(format=<schema>)` call to assemble the final outline |
| Input persistence | Pydantic `CourseGenerationRequest` saved as typed JSONB on the `Course` row |
| Schema rigor | **ID-based cross-references** with post-generation validation (broken refs → `needs_review`, not rejection) |
| Regeneration (v1) | Full regenerate only. Per-module / per-lesson regen is an explicit fast-follow |
| Form fields | Topic, current_expertise, target_expertise, age_category, hours range (min/max), included_resources (multi-select), learner_context (optional free text) |
| Navigation | New top-level "Courses" sidebar section at the same level as Chats and Projects |
| Model used | User's `Settings.default_model` (per-course override is a fast-follow) |
| Export | JSON view + Download JSON button in v1 (markdown export is a fast-follow) |
| Generation gate | "Generate" disabled if selected project's RAG config is incomplete; link to project settings |

### 0.2 How to use this plan

- Execute phases **in order**. Each phase has a Verification subsection — run those before moving on.
- After a phase's verification passes, **make a single commit** per the cadence in §0.4. Do not bundle multiple phases into one commit.
- If a verification fails, **stop and report**. Do not patch past the failure with additional unrelated changes, and do not commit until the failure is resolved.
- File paths are absolute or rooted at the repo. Code samples are illustrative — match the repo's existing style if there's a conflict.
- If you are unsure about a behavior the plan doesn't pin, prefer reading the existing analogous code (called out at each step) over inventing.
- **Do not exceed scope.** Items in §13 are explicit fast-follows; skip them. Items in §14 are explicit non-goals; refuse them.

### 0.3 Conventions in this repo (read before starting)

- Pydantic v2 (use `model_config = ConfigDict(...)`, `field_validator`, `Field(...)`).
- SQLAlchemy 2 async ORM with `Mapped[]` annotations. Async sessions everywhere. Alembic is the migration source of truth.
- FastAPI: `Depends(get_current_user)`, `Depends(get_db)`. Every user-scoped row queries with `user_id == current_user.id`.
- Streaming is `application/x-ndjson`, one JSON object per `\n`-terminated line.
- React Router 7 routes (no global `viewType`). Zustand stores (no React Context). Vitest + jest-dom for frontend tests.
- Design tokens in `frontend/src/styles/theme.css`. Primitives in `frontend/src/components/common/`. Material Symbols Outlined for icons via `<Icon name="…" />`.
- Migrations: `make migrate message="..."`, `make migrate-up`, `make migrate-down`.

### 0.4 Commit cadence

After each phase's verification passes, make **one** commit using a Conventional Commits message scoped to `courses`. Do not bundle multiple phases. Do not skip commits. If a verification fails, do not commit — fix the issue first, then commit.

Use explicit paths in `git add` (e.g., `git add backend/app/db/models/course.py backend/app/alembic/versions/<rev>_add_courses_table.py`); avoid `git add .` or `git add -A` to keep unrelated changes out of the commit.

| Phase | Commit message |
| --- | --- |
| 1 | `feat(courses): add Course model and migration` |
| 2 | `feat(courses): add Pydantic schemas for input and outline` |
| 3 | `feat(courses): add research and assembly prompt templates` |
| 4 | `feat(courses): add course generation service (two-step pipeline)` |
| 5 | `feat(courses): add courses API endpoints with streaming generation` |
| 6 | `test(courses): add backend test coverage` |
| 7 | `feat(courses): add frontend types, services, store, and generation hook` |
| 8 | `feat(courses): add frontend components` |
| 9 | `feat(courses): wire courses routes and sidebar section` |
| 10 | `test(courses): add frontend test coverage` |

Phase 11 is manual end-to-end verification — no commit. If regressions surface during Phase 11, fix them with focused `fix(courses): …` commits.

---

## Phase 1 — Database: `Course` model + migration

### Goal
Add the `courses` table with proper FK constraints and indexes.

### Files to create
- `backend/app/db/models/course.py`

### Files to modify
- `backend/app/db/models/__init__.py` (export `Course`)

### Steps

1. In `backend/app/db/models/course.py` define a Python enum `CourseStatus` with values `pending`, `generating`, `complete`, `needs_review`, `failed`.
2. Define the `Course` SQLAlchemy model with columns:
   - `id: UUID` PK, default `uuid4` — match the UUID pattern in `chat.py` / `project.py`.
   - `user_id: UUID` FK → `users.id`, NOT NULL, indexed, `ondelete="CASCADE"`.
   - `project_id: UUID` FK → `projects.id`, NOT NULL, indexed, `ondelete="CASCADE"`.
   - `title: str(256)` NOT NULL — initialized from `input.topic` at creation; user-editable later.
   - `status: CourseStatus` NOT NULL, default `pending` (use SQLAlchemy `Enum(CourseStatus, name="course_status")`).
   - `input: JSONB` NOT NULL — serialized `CourseGenerationRequest`.
   - `outline: JSONB` nullable — serialized `CourseOutline` once generated.
   - `validation_errors: JSONB` nullable — list of `{path, msg}` dicts.
   - `model_used: str(128)` nullable — Ollama model id used at generation time.
   - `created_at`, `updated_at` — `TIMESTAMP WITH TIME ZONE`, server defaults `now()`. Mirror `Chat`.
   - `generated_at` — same type, nullable, set when status transitions to complete/needs_review.
3. No back-population relationships required on `Project` or `User` unless needed by an endpoint. Skip for now (add only when reading code that needs `project.courses`).
4. Export `Course` and `CourseStatus` from `backend/app/db/models/__init__.py`.

### Generate the Alembic migration
1. `make migrate message="add courses table"`
2. Open the generated revision file under `backend/app/alembic/versions/`. Verify:
   - The PostgreSQL enum `course_status` is created.
   - The two FKs use `ondelete='CASCADE'`.
   - The two FK columns are indexed.
   - JSONB columns are typed as `postgresql.JSONB`.
3. If Alembic missed any of the above (especially the enum), edit the migration to add them by hand. The downgrade step must reverse the enum creation.

### Verification
```bash
make migrate-up          # applies cleanly
make migrate-down        # reverses cleanly
make migrate-up          # idempotent re-apply
make shell-db
# in psql:
\d courses               # confirm schema
\dT+ course_status       # confirm enum values
```
Acceptance: schema matches the spec above; up/down/up cycle is clean.

---

## Phase 2 — Pydantic schemas (input + output + API)

### Goal
Define typed schemas. `CourseOutline.model_json_schema()` will be fed to Ollama's `format=` parameter, so the JSON Schema must validate cleanly.

### Files to create
- `backend/app/schemas/course.py`

### Files to modify
- `backend/app/schemas/__init__.py` (re-exports)

### Steps

1. **Enums** (Python `str`-Enum so they serialize to JSON strings):
   - `ExpertiseLevel`: `none`, `novice`, `competent`, `proficient`, `expert`
   - `AgeCategory`: `primary` (grade 1-3), `elementary` (grade 4-7), `junior_high` (8-9), `senior_high` (10-12), `college`, `bachelors`, `masters`, `phd`
   - `ResourceType`: `readings`, `practice_questions`, `quizzes`, `projects`
   - `BloomLevel`: `remember`, `understand`, `apply`, `analyze`, `evaluate`, `create`
   - `AssessmentType`: `quiz`, `practice_question`, `project`, `reflection`
2. **Input schema** — `CourseGenerationRequest`:
   - `topic: str` (min 2, max 200)
   - `current_expertise: ExpertiseLevel`
   - `target_expertise: ExpertiseLevel`
   - `age_category: AgeCategory`
   - `hours_min: int` (≥1, ≤500)
   - `hours_max: int` (≥1, ≤500)
   - `included_resources: list[ResourceType]` (default `[]`)
   - `learner_context: str | None` (max 1000)
   - **Validators**:
     - `hours_max >= hours_min`
     - `target_expertise >= current_expertise` (ordered by enum position)
3. **Output schema** — IDs everywhere, all unique, slug-style (`mod-1`, `les-1-1`, `obj-1-1-1`, `out-c-1`, `asm-1-1-1`):
   - `Outcome { id, text, bloom_level }`
   - `Objective { id, text, bloom_level }`
   - `Reading { title, url, snippet? }`
   - `Assessment { id, type, prompt, assesses_outcome_ids: list[str] (min 1) }`
   - `Lesson { id, title, summary, estimated_hours: float > 0, objectives: list[Objective] (min 1), prerequisite_ids: list[str] (default []), readings: list[Reading] (default []), assessments: list[Assessment] (default []) }`
   - `Module { id, title, summary, estimated_hours: float > 0, outcomes: list[Outcome] (min 1), lessons: list[Lesson] (min 1) }`
   - `CourseOutline { title, summary, target_audience, total_hours: float > 0, course_outcomes: list[Outcome] (min 1), modules: list[Module] (min 1) }`
   - Each Pydantic model must include `model_config = ConfigDict(extra="forbid")` so unexpected fields raise.
4. **API schemas**:
   - `CourseCreate { project_id: UUID, input: CourseGenerationRequest }`
   - `CourseUpdate { title?: str }`
   - `CourseRegenerateRequest { input?: CourseGenerationRequest }` (when present, overwrites saved input before regenerating)
   - `CourseResponse { id, user_id, project_id, title, status, input, outline?, validation_errors?, model_used?, created_at, updated_at, generated_at? }`
   - `CourseListItem { id, title, project_id, status, total_hours?, created_at, updated_at, generated_at? }`

### Verification
```bash
make shell-backend
python -c "
from app.schemas.course import CourseOutline, CourseGenerationRequest
import json
print(json.dumps(CourseOutline.model_json_schema(), indent=2)[:500])
print(CourseGenerationRequest(topic='X', current_expertise='novice', target_expertise='competent', age_category='elementary', hours_min=4, hours_max=6))
"
```
Acceptance: JSON Schema output is valid (no Pydantic errors); a sample request constructs without raising; invalid request (`hours_max < hours_min`) raises `ValidationError`.

---

## Phase 3 — Prompt templates

### Goal
Two markdown prompt files: one for the phase-1 research agent, one for the phase-2 structured-output assembly.

### Files to create
- `backend/app/prompts/course_research_agent.md`
- `backend/app/prompts/course_assembly.md`

### `course_research_agent.md` — Phase-1 system prompt
Audience: an LLM with the `search_wikipedia` tool available.

Required content (paraphrase, don't copy verbatim):

> You are a curriculum-research assistant. Your job is to produce **research notes**, not the final course outline.
>
> Inputs:
> - Topic: `{topic}`
> - Student audience: `{age_category}` (`{age_description}`)
> - Current expertise: `{current_expertise}` · Target expertise: `{target_expertise}`
> - Target study hours: `{hours_min}–{hours_max}`
> - Included resources: `{included_resources}`
> - Learner context: `{learner_context}`
>
> Process:
> 1. Sketch a candidate module/lesson breakdown sized for the target hours and audience.
> 2. For each candidate lesson, call `search_wikipedia` (1–3 focused queries per lesson) to find articles that map to the lesson's content.
> 3. After ~3-5 tool calls per module — or sooner if confident — stop and emit your research summary as plain text. The summary should include:
>    - Final module list (titles + one-sentence gloss)
>    - For each module: lesson list (titles + one-sentence gloss + a single best Wikipedia article: full title and URL)
>    - Any prerequisite ordering you noticed
>
> Do **not** emit JSON. Do **not** invent Wikipedia URLs — only cite articles returned by the tool. If a search returns nothing relevant, say so and pick a closely related article instead.

Substitute the template fields at runtime in `course_service.py`. Provide `{age_description}` as a human string (e.g., `"primary school (grade 1-3)"`) — make this a small helper in `course_service.py`.

### `course_assembly.md` — Phase-2 system prompt
Audience: an LLM in `format=<json_schema>` mode (no tools).

Required content (paraphrase):

> You are a curriculum architect. You will be given research notes from a prior assistant and a set of course parameters. Produce a structured `CourseOutline` JSON conforming exactly to the provided JSON schema.
>
> Apply backward design:
> 1. State 3–6 course-level outcomes covering what a graduate will be able to do.
> 2. For each module, state 2–4 module outcomes that decompose the course outcomes.
> 3. For each lesson, state 1–4 objectives using Bloom's taxonomy action verbs at the right cognitive level for the target expertise.
> 4. Every objective must be exercised by ≥1 assessment in the same lesson. Assessments must list `assesses_outcome_ids` referencing outcomes by id.
> 5. Each lesson's `prerequisite_ids` reference *previously declared* lessons or modules — never forward references.
>
> Rules:
> - Use short unique slugs for IDs: `out-c-1` (course outcome), `mod-1`, `out-m-1-1` (module outcome), `les-1-1`, `obj-1-1-1`, `asm-1-1-1`.
> - All Wikipedia readings must come from the supplied research notes; do not invent URLs.
> - `total_hours` is the sum of all module `estimated_hours` and must fall within `{hours_min}–{hours_max}`.
> - Include assessments only of types the user requested in `included_resources` (e.g., if `quizzes` is not requested, do not emit `assessment.type = "quiz"`).
>
> Output the JSON object only — no prose before or after.

### Verification
Both files exist; manually read each to confirm no leftover placeholder text and no contradictions with the schema definitions in Phase 2.

---

## Phase 4 — Service layer

### Goal
Wire the two-step pipeline.

### Files to modify
- `backend/app/services/agent_service.py` — parameterize `run_agent`
- `backend/app/services/ollama_service.py` — add `chat_structured`

### Files to create
- `backend/app/services/course_service.py`

### 4a. Refactor `run_agent`

Find the function signature in `agent_service.py` (currently `~line 268`). Add a keyword-only parameter:

```python
async def run_agent(
    *,
    chat: Chat,
    db: AsyncSession,
    user_message_content: str,
    model: str,
    settings: Settings,
    max_iters: int = 5,
    system_prompt: str | None = None,   # NEW
) -> AsyncIterator[dict]:
    ...
```

Inside the function, find the existing assignment that uses `AGENT_SYSTEM_PROMPT` (~line 297). Replace it with:

```python
prompt = system_prompt or AGENT_SYSTEM_PROMPT
```

Do not change any other behavior. All existing callers will continue to pass no `system_prompt` and get the existing default.

### 4b. Add `chat_structured` to `OllamaService`

In `ollama_service.py`, add a new method:

```python
async def chat_structured(
    self,
    *,
    model: str,
    messages: list[dict],
    json_schema: dict,
    options: dict | None = None,
) -> str:
    """Run a single non-streaming chat with `format=<json_schema>`. Returns the raw JSON string from the model."""
    response = await self.client.chat(
        model=model,
        messages=messages,
        format=json_schema,
        options=options or {},
        stream=False,
    )
    return response.message.content
```

Do not parse JSON or validate here — the caller does that. This keeps `ollama_service` schema-agnostic.

### 4c. Build `course_service.py`

Public function:

```python
async def generate_course(
    *,
    course: Course,
    db: AsyncSession,
    settings: Settings,
) -> AsyncIterator[dict]:
    """Drive the two-step pipeline. Yields frames (dicts). Persists outline on completion."""
```

Pipeline (in order):

1. **Hydrate input.** `request = CourseGenerationRequest.model_validate(course.input)`.
2. **RAG gate.** Load `course.project` (eager or separate query). If RAG config is incomplete (`rag_enabled is False`, or missing `rag_server_id` / `rag_corpus_id`), yield `{"type":"error","message":"Project RAG config is incomplete; configure it before generating."}` and return.
3. **Status → generating.** Set `course.status = generating`, commit.
4. **Phase 1: research.** Yield `{"type":"phase","name":"research"}`.
   - Build the phase-1 system prompt by loading `prompts/course_research_agent.md` and substituting `{topic}`, `{age_category}`, `{age_description}`, `{current_expertise}`, `{target_expertise}`, `{hours_min}`, `{hours_max}`, `{included_resources}` (comma-joined), `{learner_context}` (or `"none provided"`).
   - Build a dummy `Chat`-like context that `run_agent` needs. Two options:
     - **Preferred:** create a transient in-memory chat object that is *not* persisted, with `agent_mode_enabled=True` and `project_id=course.project_id`, and pass that. Check whether `run_agent` writes any DB state on this object before relying on this; if it does, fall back to option B.
     - **Fallback:** introduce a thin wrapper `run_agent_for_course` that accepts the `project` directly and constructs the system-prompt/tool plumbing without needing a `Chat`. Document the reason inline.
   - Call `run_agent(..., system_prompt=<rendered phase-1 prompt>, user_message_content="Research and plan the course.")`. Forward every yielded frame to the caller unchanged. Accumulate any `chunk.content` into a local `research_notes` string.
   - If `run_agent` ends with `{"type":"error",...}`, persist `course.status=failed`, persist `validation_errors=[{"path":"phase-1","msg":...}]`, yield `{"type":"done","status":"failed"}`, return.
5. **Phase 2: assembly.** Yield `{"type":"phase","name":"assembling"}`.
   - Load `prompts/course_assembly.md`, substitute the same fields.
   - Build messages:
     ```python
     messages = [
         {"role": "system", "content": rendered_assembly_prompt},
         {"role": "user", "content": f"Research notes:\n{research_notes}\n\nProduce the CourseOutline JSON."},
     ]
     ```
   - Call `ollama_service.chat_structured(model=<settings.default_model>, messages=messages, json_schema=CourseOutline.model_json_schema())`.
   - Parse: `outline = CourseOutline.model_validate_json(raw)`. On `ValidationError`: persist `status=failed`, persist `validation_errors=[{"path":"phase-2","msg":<exc>}]`, yield `done` with `status=failed`, return.
6. **Validation.** `errors = validate_outline(outline, request)` (see 4d). If `errors`, `status = needs_review`; else `status = complete`.
7. **Persist.** Save `course.outline = outline.model_dump()`, `course.validation_errors = errors or None`, `course.model_used = settings.default_model`, `course.generated_at = utcnow()`, commit.
8. **Emit final frames.**
   - `{"type":"outline","content": outline.model_dump()}`
   - If `errors`: `{"type":"validation","errors": errors}`
   - `{"type":"done","status": course.status.value}`

### 4d. Validation function

```python
def validate_outline(outline: CourseOutline, request: CourseGenerationRequest) -> list[dict]:
    errors: list[dict] = []

    outcome_ids = {o.id for o in outline.course_outcomes}
    for m in outline.modules:
        outcome_ids |= {o.id for o in m.outcomes}

    seen_lesson_ids: set[str] = set()
    seen_module_ids: set[str] = set()
    for mi, module in enumerate(outline.modules):
        for li, lesson in enumerate(module.lessons):
            for pid in lesson.prerequisite_ids:
                if pid not in seen_lesson_ids and pid not in seen_module_ids:
                    errors.append({
                        "path": f"modules[{mi}].lessons[{li}].prerequisite_ids",
                        "msg": f"unknown prerequisite '{pid}'",
                    })
            for ai, asm in enumerate(lesson.assessments):
                for oid in asm.assesses_outcome_ids:
                    if oid not in outcome_ids:
                        errors.append({
                            "path": f"modules[{mi}].lessons[{li}].assessments[{ai}].assesses_outcome_ids",
                            "msg": f"unknown outcome '{oid}'",
                        })
            seen_lesson_ids.add(lesson.id)
        seen_module_ids.add(module.id)

    total = sum(l.estimated_hours for m in outline.modules for l in m.lessons)
    if not (request.hours_min <= total <= request.hours_max):
        errors.append({
            "path": "modules[*].lessons[*].estimated_hours",
            "msg": f"total {total}h not in [{request.hours_min}, {request.hours_max}]",
        })

    return errors
```

### Verification
- `make lint` passes.
- Unit test the validator in isolation (added in Phase 6) with hand-crafted fixtures.
- No call sites of `run_agent` elsewhere break (search the repo to confirm).

---

## Phase 5 — API endpoints

### Goal
Expose CRUD + generate + regenerate as a versioned router.

### Files to create
- `backend/app/api/v1/endpoints/courses.py`

### Files to modify
- `backend/app/api/v1/router.py` (register the courses router; mirror how `chats`, `projects`, `messages`, `settings`, `models` are registered)

### Endpoints

#### `POST /api/v1/courses` — create
- Body: `CourseCreate` (`project_id`, `input`).
- Verify project belongs to current user. If not, 404.
- Verify project has complete RAG config. If not, 422 with a clear message.
- Insert Course with `status=pending`, `title=input.topic`.
- Return `CourseResponse`.

#### `POST /api/v1/courses/{course_id}/generate` — stream generation
- `StreamingResponse(media_type="application/x-ndjson")`.
- Implementation: mirror the pattern at `backend/app/api/v1/endpoints/messages.py:864-868` (open a fresh DB session inside the streaming generator; poll `request.is_disconnected()`).
- Inside the generator, iterate over `course_service.generate_course(course=..., db=..., settings=...)`, NDJSON-encode each frame (`json.dumps(frame) + "\n"`).
- On client disconnect mid-stream: set `status=failed`, persist, stop yielding.

#### `POST /api/v1/courses/{course_id}/regenerate` — full regenerate
- Body: optional `CourseRegenerateRequest`. If `input` is present, validate (it's a full `CourseGenerationRequest`) and overwrite `course.input`.
- Reset `outline=None`, `validation_errors=None`, `status=pending`, `generated_at=None`, commit.
- Return the same streaming response as `/generate` (delegating to the same generator function).

#### `GET /api/v1/courses` — list
- Returns `list[CourseListItem]`, user-scoped, ordered by `created_at` desc.
- `total_hours` field is derived from `outline` if present (sum of lesson hours).

#### `GET /api/v1/courses/{course_id}` — detail
- Returns `CourseResponse`, user-scoped, 404 if not owned.

#### `PATCH /api/v1/courses/{course_id}` — rename
- Body: `CourseUpdate` (`title?`). Updates `title` only in v1.

#### `DELETE /api/v1/courses/{course_id}` — hard delete
- 204 on success.

### Verification

Smoke test from `make shell-backend` once endpoints are wired (or via the running dev server):

```bash
# Create a course (assumes a project with RAG configured)
curl -s -X POST http://backend:8000/api/v1/courses \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "<uuid>", "input": {"topic": "Photosynthesis", "current_expertise": "novice", "target_expertise": "competent", "age_category": "elementary", "hours_min": 4, "hours_max": 6, "included_resources": ["readings", "quizzes"]}}'

curl -s http://backend:8000/api/v1/courses                # list
curl -s http://backend:8000/api/v1/courses/<id>           # detail
curl -s -X PATCH http://backend:8000/api/v1/courses/<id> -H 'Content-Type: application/json' -d '{"title": "Photosynthesis 101"}'
curl -s -X DELETE http://backend:8000/api/v1/courses/<id>
```

Acceptance: all six endpoints respond as specified; user-scoping rejects cross-user IDs with 404; bad RAG config returns 422 with a guidance message.

---

## Phase 6 — Backend tests

### Goal
pytest coverage matching the style of existing `backend/app/tests/test_api/`.

### Files to create
- `backend/app/tests/test_api/test_courses.py`

### Required test classes and cases

```python
class TestCourseCRUD:
    test_create_course_persists_with_pending_status
    test_create_course_fails_if_project_has_incomplete_rag
    test_create_course_fails_if_project_belongs_to_other_user   # placeholder until Phase 7
    test_list_returns_user_courses_only
    test_get_returns_outline_after_generation
    test_patch_title_updates_record
    test_delete_removes_record

class TestCourseGeneration:
    test_generate_streams_phase_chunks_and_done
    test_generate_persists_outline_on_success
    test_generate_sets_needs_review_on_validation_failure
    test_generate_sets_failed_on_parse_error
    test_generate_aborts_on_incomplete_rag

class TestRegenerate:
    test_regenerate_preserves_id_and_replaces_outline
    test_regenerate_with_input_override_persists_new_input
    test_regenerate_resets_status_to_pending_then_completes

class TestValidator:
    test_validator_flags_unknown_prerequisite_id
    test_validator_flags_unknown_outcome_id_in_assessment
    test_validator_flags_hours_out_of_range
    test_validator_returns_empty_on_valid_outline
    test_validator_allows_module_id_as_prerequisite
```

### Mocking guidance
- Mock `agent_service.run_agent` to yield a deterministic sequence: a few `chunk` frames whose `content` accumulates into a fixed `research_notes` string. End with a clean `done` frame.
- Mock `ollama_service.chat_structured` to return a hand-crafted valid `CourseOutline` JSON string. For failure paths, return malformed JSON or JSON missing required fields.
- For validator tests, build `CourseOutline` instances directly with hand-crafted broken refs.

### Fixtures needed
- `course_user` (default seeded user)
- `course_project` (a Project owned by `course_user` with complete RAG config — a `RagServer` row plus `rag_enabled=True`, `rag_corpus_id`, `rag_top_k`)
- `pending_course` (Course row with `status=pending`)
- `valid_outline_dict` (a small but schema-conformant CourseOutline)

### Verification
```bash
make test                                                # full suite green
pytest backend/app/tests/test_api/test_courses.py -v     # focused green
```

---

## Phase 7 — Frontend foundations (types, services, store, hook)

### Files to create
- `frontend/src/types/course.ts`
- `frontend/src/services/courseApi.ts`
- `frontend/src/services/courseStreamApi.ts`
- `frontend/src/stores/courseStore.ts`
- `frontend/src/hooks/useCourseGeneration.ts`

### `types/course.ts`
Hand-mirror Pydantic schemas as TypeScript types. Keep enums as string-union types (e.g., `'novice' | 'competent' | …`). Include `CourseStatus`, `CourseGenerationRequest`, `CourseOutline`, `Module`, `Lesson`, `Outcome`, `Objective`, `Reading`, `Assessment`, `Course`, `CourseListItem`, `CourseRegenerateRequest`, and a `GenerationFrame` discriminated union covering all NDJSON frame types: `phase`, `chunk`, `tool_call`, `tool_result`, `outline`, `validation`, `done`, `error`.

### `services/courseApi.ts`
Mirror `services/projectApi.ts`. Axios-based methods: `list`, `get(id)`, `create(body)`, `update(id, body)`, `remove(id)`.

### `services/courseStreamApi.ts`
Mirror `services/streamApi.ts`. Raw `fetch` to `/courses/{id}/generate` and `/courses/{id}/regenerate`. Yields parsed `GenerationFrame` objects via an async iterator. Handle disconnect on abort signal.

### `stores/courseStore.ts`
Zustand store. State: `courses: CourseListItem[]`, `coursesById: Record<string, Course>`, `loading: boolean`. Actions: `loadList()`, `loadOne(id)`, `upsert(course)`, `remove(id)`. Export `useCoursesAutoLoad()` that calls `loadList()` on mount. Mirror `projectsStore.ts` patterns exactly.

### `hooks/useCourseGeneration.ts`
Owns generation-time state for a single course:
```ts
type GenState = {
  phase: 'idle' | 'research' | 'assembling' | 'done' | 'error';
  researchChunks: string;            // accumulated chunk frames
  toolCalls: ToolCallTraceEntry[];   // mirror agent's tool_call/tool_result entries
  outline: CourseOutline | null;
  validationErrors: ValidationError[] | null;
  finalStatus: CourseStatus | null;
  error: string | null;
};
```
Exposes `start()` (calls `courseStreamApi.generate(...)` and pumps frames into state) and `cancel()` (aborts via `AbortController`). Mirrors `useStreaming.ts` patterns; capture `onComplete` via a ref so callers can pass inline closures.

### Verification
`docker exec ollama_frontend npm test` continues to pass (no tests yet for these — verification is "doesn't break the build").

---

## Phase 8 — Frontend components

### Files to create
- `frontend/src/components/courses/CourseList.tsx`
- `frontend/src/components/courses/NewCourseForm.tsx`
- `frontend/src/components/courses/CourseDetail.tsx`
- `frontend/src/components/courses/OutlineRenderer.tsx`
- `frontend/src/components/courses/ResearchTrace.tsx`

### `CourseList.tsx`
List view at `/courses`. Cards or rows showing title, project name, status badge, total hours (if available), created_at. Click → navigate to `/courses/:id`. Header has "+ New Course" button → `/courses/new`. Empty state explains how to start.

### `NewCourseForm.tsx`
Form mounted at `/courses/new`. Fields:
- **Project**: `<Select>` populated from `projectsStore`, filtered to projects with complete RAG config. Disabled-state explains why a project isn't selectable.
- **Topic**: text input, required.
- **Current expertise** + **Target expertise**: two `<Select>` controls (5 enum values each).
- **Age category**: `<Select>` (8 values, with human-readable labels).
- **Hours (min and max)**: two `<input type="number">` side-by-side; client-side validation `max ≥ min`.
- **Included resources**: multi-select checkboxes (4 values).
- **Learner context** (optional): `<textarea>`, max 1000 chars, with a char counter.
- **Submit**: POST `/courses`, then `navigate('/courses/' + id, { state: { autoStart: true }})` so `CourseDetail` auto-fires generation.
- **Soft warnings**: show non-blocking notices for suspicious combinations (e.g., primary + masters); use `<ToastContainer>` or an inline banner. Never block submit on these.

### `CourseDetail.tsx`
Route `/courses/:courseId`. Branching by `course.status`:
- `pending`: show "Generate" button.
- `generating`: show `<ResearchTrace>` + phase indicator.
- `complete`: show `<OutlineRenderer>` + actions toolbar.
- `needs_review`: same as complete, plus a yellow banner listing `validation_errors`.
- `failed`: error message + Retry button (triggers regenerate).

Actions toolbar: Regenerate (opens confirm dialog), Edit Title (inline), Delete (uses `<ConfirmDialog>`), Download JSON (anchor with `Blob` href).

If route state has `{ autoStart: true }`, fire `useCourseGeneration().start()` on mount once.

### `OutlineRenderer.tsx`
Pure, recursive. Receives `outline: CourseOutline`. Layout:
- Course header: title, summary, target_audience, total_hours, course-level outcomes (each with Bloom's badge using `--brand-tint`).
- Module sections (collapsible, default expanded): title, summary, hours, module outcomes, then lessons.
- Lessons: title, summary, hours. Sub-sections for objectives (with Bloom's badges), prerequisites (chips with the referenced lesson title, clickable → scrolls), readings (external `<a>` tags with the favicon-style Wikipedia icon), assessments (typed badges).
- Build an ID-→-lesson lookup map for prerequisite resolution.

### `ResearchTrace.tsx`
Mirror visual language of `ToolCalls.tsx`: collapsible header showing phase + tool call count, expandable body listing each `tool_call` / `tool_result` pair. Auto-expand during streaming, collapse on `done` frame. Show the chunked research text below the tool list (monospace, dim).

### Verification
- `make dev` runs; navigate manually: `/courses`, `/courses/new`, `/courses/:id`.
- No console errors during render of an empty list, the new-course form, and a finished course.

---

## Phase 9 — Routing + sidebar integration

### Files to modify
- `frontend/src/router.tsx`
- `frontend/src/components/sidebar/Sidebar.tsx`
- `frontend/src/App.tsx`

### Steps
1. Add routes (mirror project routes):
   - `/courses` → `CourseList`
   - `/courses/new` → `NewCourseForm`
   - `/courses/:courseId` → `CourseDetail`
2. Add a new sidebar section titled "Courses" between Chats and Projects (or after Projects — mirror visual hierarchy). Header has "+ New" affordance linking to `/courses/new`. Below: list of courses with status indicator; active route highlighted.
3. In `App.tsx`, mount `useCoursesAutoLoad()` alongside `useProjectsAutoLoad()` and `useSettingsAutoLoad()`.

### Verification
- Navigation works without 404s.
- Active highlighting matches what Chats and Projects do.

---

## Phase 10 — Frontend tests

### Files to create
- `frontend/src/components/courses/NewCourseForm.test.tsx`
- `frontend/src/components/courses/OutlineRenderer.test.tsx`
- `frontend/src/hooks/useCourseGeneration.test.tsx`

### Tests
- **NewCourseForm**: required-field validation, hours validation (`max ≥ min`), submit calls `coursesApi.create` and `navigate(...)`, project dropdown excludes RAG-incomplete projects.
- **OutlineRenderer**: renders nested course → modules → lessons; prerequisite chip click scrolls (mock `scrollIntoView`); Bloom's badges render with correct labels; readings open in new tab.
- **useCourseGeneration**: feeds a sequence of mock `GenerationFrame` objects through the hook and asserts state transitions in order; verifies error frames surface correctly; verifies `cancel()` aborts the request.

### Verification
```bash
docker exec ollama_frontend npm test
```
Acceptance: all tests pass; existing tests still pass.

---

## Phase 11 — End-to-end manual verification

Execute after Phase 10 passes.

1. `make dev`
2. Ensure Ollama on the host has a model that supports both `tools=` and `format=` (recommended: `llama3.1`, `llama3.2`, or `qwen2.5`). Validate with a one-off probe in `make shell-backend` if unsure.
3. In the UI: create or open a Project; configure its RAG server (URL + corpus_id pointed at a Wikipedia-style corpus); enable RAG.
4. Sidebar → Courses → "+ New Course". Fill:
   - Topic: "Photosynthesis"
   - Age: Elementary (grade 4-7)
   - Current expertise: Novice
   - Target expertise: Competent
   - Hours: 4 – 6
   - Resources: Readings, Quizzes
   - Submit.
5. Watch the Research Trace pane:
   - Phase indicator transitions: Research → Assembling → Done.
   - ≥1 `search_wikipedia` call per planned lesson.
   - Tool calls show OK badges.
6. Outline view checks:
   - Each lesson has 1–4 objectives with Bloom's badges at the right cognitive level for "competent".
   - Prerequisite chips are clickable and scroll to the referenced lesson.
   - Reading URLs open Wikipedia articles in a new tab.
   - `total_hours` summary is within 4–6, or a `needs_review` banner shows a hours warning.
   - Assessments link back to declared outcomes (chip text reads the outcome's first words).
7. Regenerate from the same Course; verify previous outline is replaced, course `id` is preserved in the URL, `generated_at` updates.
8. Try a course on a project with incomplete RAG: confirm Generate is disabled and a guidance message links to the project's settings.
9. Delete the course; confirm it's removed from the sidebar list.

---

## 12. Definition of Done

- [ ] Phase 1–10 verifications all pass on a clean checkout
- [ ] `make test` green
- [ ] `docker exec ollama_frontend npm test` green
- [ ] `make lint` clean
- [ ] `make migrate-up` / `migrate-down` / `migrate-up` cycle clean
- [ ] Manual E2E (Phase 11) completes without console errors
- [ ] This plan checked into `docs/COURSE_GENERATOR_PLAN.md`
- [ ] No regressions in existing agent mode (`make test` covers it; if any agent test fails, the `run_agent` refactor in 4a is the suspect — back out the `system_prompt` parameter default)

---

## 13. Explicit fast-follows (do NOT implement in v1)

These are intentionally deferred. If you find yourself starting on one, stop.

- Per-module / per-lesson regeneration endpoints + UI
- Markdown export (rendered HTML on a print-friendly route)
- PDF export
- Outline versioning (keep last N outlines per course)
- Per-course model override (today: user's `Settings.default_model`)
- `get_article_summary` tool (only add if reading citations are noisy in practice)
- Course sharing or publishing
- Adaptive tutor mode (chat with a tutor agent that tracks progress)

---

## 14. Explicit non-goals

- Multi-user support (Phase 7 auth stays deferred)
- Light theme support (the repo is dark-only)
- MCP integration
- Switching from `simple.wikipedia.org` to `en.wikipedia.org` dynamically inside the tool — that's the RAG server's concern, not this codebase's

---

## 15. Common gotchas and guidance

- **`format=` reliability across models.** Ollama's structured output works well on llama3.x and qwen2.5; older or smaller models may emit invalid JSON despite the schema. If `model_validate_json` fails frequently, the right next step is to log the raw response (and the model used) and either swap models or add a retry with a stricter prompt. Do not add brittle text-extraction parsing.
- **Tool use + `format=` in one call.** Avoid combining them. The two-step pipeline exists specifically because mixing `tools=` and `format=` in a single Ollama call is fragile.
- **Agent loop `max_iters=5`.** For larger courses, the model may run out of iterations before researching every lesson. If validation `needs_review` is consistently flagged with thin readings, the right intervention is to raise `max_iters` for course research only (parameterize via a kwarg to `run_agent`) — not to remove the cap globally.
- **Citation aggregation.** `run_agent` aggregates citations internally as `aggregated_citations`. v1 simply parses the research notes (the model writes URLs into the text). If quality drops, the better path is to expose `aggregated_citations` as a final summary frame from `run_agent` and consume that directly.
- **NDJSON framing.** Mirror `messages.py:864-868` exactly for the StreamingResponse generator. Don't invent new frame shapes; if you need a new frame type, extend the `GenerationFrame` union in TS and the matching dict shape in Python in lockstep.
- **System prompt placement in `run_agent`.** The override must replace the default before the messages list is built; otherwise tool-calling degrades on some models.
- **RAG validation gate is checked twice.** At `POST /courses` creation and at `POST /courses/{id}/generate`, because the project's RAG config can change between create and generate. Don't rely on one alone.
- **Status transitions.** `pending → generating → (complete | needs_review | failed)`. Only `regenerate` may move backwards (it resets to `pending`).
- **User scoping.** Every Course query MUST filter by `user_id == current_user.id`. Use the patterns from `endpoints/chats.py` and `endpoints/projects.py`. Phase 7 auth isn't built yet but the FK is real today.
- **Frontend types are hand-mirrored.** This repo has no OpenAPI-to-TS step. When you change a Pydantic schema, change the TS type in the same commit.
- **Hot reload caveat.** Backend hot reload doesn't always pick up new SQLAlchemy enum types cleanly. After Phase 1, restart the backend container (`make down && make dev`) before testing endpoints that touch the new enum.
