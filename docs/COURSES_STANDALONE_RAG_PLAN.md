# Standalone Courses — Decouple from Projects

> Canonical location post-approval: `docs/COURSES_STANDALONE_RAG_PLAN.md` (per the user's plan-location preference).
> Predecessor: `docs/COURSE_GENERATOR_PLAN.md` (the v1 plan that scoped courses to projects).

## Context

The course generator that just shipped requires every Course to belong to a Project, and reads RAG config (`rag_server_id`, `rag_top_k`) off the Project. That made v1 simpler — no new RAG plumbing — but creates user-facing friction: you can't generate a course unless you've already created a Project, enabled RAG on it, and picked a server.

This change makes Courses **first-class** and standalone. Each Course carries its own `rag_server_id` + `rag_top_k`, and `project_id` is removed from the courses table. The "New Course" form picks a RAG server directly — no project needed (and a course can be created against a fresh DB with zero projects).

## Locked design decisions

| Axis | Decision |
| --- | --- |
| `Course.project_id` | **Dropped entirely**. Not made nullable. Courses are first-class. |
| New columns on `courses` | `rag_server_id: UUID FK (rag_servers.id) ON DELETE SET NULL, NOT NULL`; `rag_top_k: int, NOT NULL`. |
| Existing rows | Migration backfills the new columns by joining through `projects` before dropping `project_id`. Any row whose project lacked RAG config gets deleted (its FK becomes unsatisfiable). |
| `agent_service.run_agent` signature | Replaces `project: Project` with `rag_server: RagServer, rag_top_k: int`. Both call sites (chat agent + course generator) updated. |
| `_execute_search_wikipedia` | Receives `(rag_server, rag_top_k)` instead of `project`. |
| Frontend form | Project picker is replaced by a RAG server picker (sourced from `useRagServersStore`) plus a `rag_top_k` number input. |
| Empty state | If no RAG servers exist, the form shows a "No RAG servers configured — go to RAG Servers to add one" banner with a link. |
| Updating RAG on an existing course | `PATCH /courses/{id}` accepts optional `rag_server_id` / `rag_top_k`. |

## Phases

Each phase ends with a single commit per the same cadence rules from §0.4 of `docs/COURSE_GENERATOR_PLAN.md`.

### Phase 1 — DB migration

**Files to create**
- `backend/alembic/versions/<rev>_courses_drop_project_add_rag.py`

**Migration steps** (upgrade):
1. `op.add_column('courses', sa.Column('rag_server_id', UUID(as_uuid=True), nullable=True))`
2. `op.add_column('courses', sa.Column('rag_top_k', Integer, nullable=True))`
3. Backfill from project: `UPDATE courses SET rag_server_id = p.rag_server_id, rag_top_k = p.rag_top_k FROM projects p WHERE p.id = courses.project_id`
4. `DELETE FROM courses WHERE rag_server_id IS NULL OR rag_top_k IS NULL` — orphans whose backfill failed
5. `op.alter_column('courses', 'rag_server_id', nullable=False)`
6. `op.alter_column('courses', 'rag_top_k', nullable=False)`
7. `op.create_foreign_key('fk_courses_rag_server', 'courses', 'rag_servers', ['rag_server_id'], ['id'], ondelete='SET NULL')` — note: ON DELETE SET NULL conflicts with NOT NULL, so use ON DELETE RESTRICT instead. Pick **RESTRICT**: can't delete a RAG server that any course depends on; the UI surfaces it via the standard 4xx.
8. `op.create_index('ix_courses_rag_server_id', 'courses', ['rag_server_id'])`
9. `op.drop_index('ix_courses_project_id', table_name='courses')`
10. `op.drop_constraint('courses_project_id_fkey', 'courses', type_='foreignkey')`
11. `op.drop_column('courses', 'project_id')`

Downgrade reverses, with `project_id` restored as a nullable column (we can't reliably reconstruct project ownership).

**Verification**
- `make migrate-up` clean
- `make shell-db` → `\d courses` shows new columns + FK + index, no `project_id`
- `make migrate-down` then `make migrate-up` is idempotent

**Commit**: `feat(courses): standalone RAG — DB migration`

### Phase 2 — Course model + Pydantic schemas

**Files to modify**
- `backend/app/db/models/course.py`
  - Drop `project_id` field and the `project` relationship
  - Add `rag_server_id: Mapped[UUID]` (FK → `rag_servers.id` ON DELETE RESTRICT, NOT NULL, indexed)
  - Add `rag_top_k: Mapped[int]` (NOT NULL)
  - Add `rag_server: Mapped["RagServer"]` relationship
- `backend/app/schemas/course.py`
  - `CourseCreate`: replace `project_id: UUID` with `rag_server_id: UUID, rag_top_k: int = Field(..., ge=1, le=50)`
  - `CourseResponse`: drop `project_id`, add `rag_server_id`, `rag_top_k`
  - `CourseListItem`: drop `project_id`, add `rag_server_id`, `rag_top_k`
  - `CourseUpdate`: add optional `rag_server_id?`, `rag_top_k?`
  - `CourseGenerationRequest`: **unchanged** — RAG config lives on the row, not in the request body's content payload

**Verification**
- `make lint` clean
- Container restart to pick up the new SQLAlchemy column types (`make down && make dev` if hot-reload doesn't catch it)

**Commit**: `feat(courses): standalone RAG — model + schemas`

### Phase 3 — `agent_service.run_agent` refactor

**Files to modify**
- `backend/app/services/agent_service.py`
  - Function signature: replace `project: Project` with two keyword args `rag_server: RagServer, rag_top_k: int`
  - Replace the three internal uses (lines 147, 149, 283 today):
    - `project.rag_top_k or _TOOL_TOP_K_CAP` → `rag_top_k or _TOOL_TOP_K_CAP`
    - `project.rag_server` → `rag_server`
  - `_execute_search_wikipedia(args, project)` → `_execute_search_wikipedia(args, rag_server, rag_top_k)`. Update its caller (`handler(tool_input, project)` → `handler(tool_input, rag_server, rag_top_k)`)
  - `TOOLS` dict signature updates accordingly
- `backend/app/api/v1/endpoints/messages.py` (the only other call site, at line 800)
  - The agent endpoint currently passes `project=project`. Change to `rag_server=project.rag_server, rag_top_k=project.rag_top_k` (project is already eager-loaded with rag_server here)
- `backend/app/services/course_service.py`
  - `_run_research_phase` and `generate_course` already load the course; switch to `course.rag_server` + `course.rag_top_k` (not `course.project.rag_server` etc.)

**Existing tests** that exercise this refactor:
- `tests/test_api/test_agent.py` — must stay green after the call-site update
- `tests/test_api/test_courses.py` — will be updated in Phase 5; expect some failures until then

**Verification**
- `pytest tests/test_api/test_agent.py -q` green
- `pytest tests/test_api/test_courses.py -q` may have failures; that's OK, fix in Phase 5

**Commit**: `refactor(agent): replace project param with rag_server + rag_top_k`

### Phase 4 — `course_service` + endpoint changes

**Files to modify**
- `backend/app/services/course_service.py`
  - Rename `_project_has_full_rag_config(project)` → `_has_rag_context(rag_server, rag_top_k) -> bool`
  - `generate_course`: query loads course with `selectinload(Course.rag_server)` instead of nested project loading; gate on `course.rag_server is not None`
- `backend/app/api/v1/endpoints/courses.py`
  - `create_course`: replace the project lookup + RAG gate with `_validate_rag_server_owned(db, current_user, rag_server_id)`. Persist `rag_server_id`, `rag_top_k` on the Course row instead of `project_id`.
  - `update_course`: also update `rag_server_id` / `rag_top_k` when provided (with ownership validation on `rag_server_id`).
  - `generate` and `regenerate`: drop project loading; load course with `course.rag_server` eager-loaded; 422 if `rag_server is None`.
  - `list_courses`: emit `rag_server_id` + `rag_top_k` in `CourseListItem`, drop `project_id`.
  - `_load_course_or_404`: change eager-load chain to `selectinload(Course.rag_server)`.

**Existing helpers to reuse**
- `_validate_rag_server_owned` in `backend/app/api/v1/endpoints/projects.py` (~line 34) — copy it inline to `courses.py` (or lift it to `app/api/v1/endpoints/_helpers.py` and import from both); it's ~15 lines and shared semantics.

**Verification**
- With backend restarted: smoke-test from `make shell-backend`:
  - `curl -X POST /api/v1/courses` with valid `rag_server_id` succeeds (201)
  - same body without `rag_server_id` 422s (Pydantic)
  - using another user's RAG server id 422s (ownership)
  - `/generate` returns 200 NDJSON if mocks are in place — covered properly in Phase 5

**Commit**: `feat(courses): standalone RAG — service + endpoints`

### Phase 5 — Backend tests

**Files to modify**
- `backend/tests/test_api/test_courses.py`
  - Replace `_make_rag_project` with `_make_rag_server` that just creates a RAG server (no project)
  - Every CRUD + generation test changes from `project_id: ...` to `rag_server_id: ..., rag_top_k: 5`
  - Rename `test_create_course_fails_if_project_has_incomplete_rag` → `test_create_course_fails_with_missing_rag_server_id` and `test_create_course_fails_with_unowned_rag_server_id`
  - Rename `test_generate_returns_422_for_rag_incomplete_project` → `test_generate_returns_422_after_rag_server_deleted` (delete the rag server between create and generate; expect 422 because the FK is restrict). Or, simpler: `test_generate_succeeds_when_no_projects_exist_at_all` — explicitly assert `SELECT count(*) FROM projects = 0` before creating + generating a course
  - Add `test_create_course_works_with_no_projects_in_db` — the headline scenario from the user's request

**Verification**
- `pytest tests/test_api/test_courses.py -q` green (~21 tests still, with some renames)
- `make test` (full suite) green

**Commit**: `test(courses): update backend tests for standalone RAG`

### Phase 6 — Frontend (types + form + lists)

**Files to modify**
- `frontend/src/types/course.ts`
  - `Course`: drop `project_id`, add `rag_server_id: string`, `rag_top_k: number`
  - `CourseListItem`: drop `project_id`, add `rag_server_id`, `rag_top_k`
  - `CourseCreate`: replace `project_id: string` with `rag_server_id: string, rag_top_k: number`
  - `CourseUpdate`: add optional `rag_server_id?: string`, `rag_top_k?: number`
- `frontend/src/services/courseApi.ts` — no shape change (it forwards bodies)
- `frontend/src/stores/courseStore.ts` — `_toListItem` drops `project_id`, adds `rag_server_id` / `rag_top_k`
- `frontend/src/components/courses/NewCourseForm.tsx` — biggest change:
  - Use `useRagServersStore` (already auto-loaded by `App.tsx`)
  - Picker shows RAG servers (label = `${name} (${corpus_id})`) instead of projects
  - Add a `rag_top_k` number input (default 5, min 1, max 50)
  - Empty state when `servers.length === 0`: "No RAG servers configured — go to RAG Servers to add one." with a button linking to `/rag-servers`
  - Drop the audience-warning logic if it's still tied to project context (it isn't today)
- `frontend/src/components/courses/CourseList.tsx` — drop any project_id reference (none rendered today; safe)
- `frontend/src/components/courses/CourseDetail.tsx` — drop any project_id reference (none rendered today; safe)

**Existing utilities reused**
- `useRagServersStore` (`frontend/src/stores/ragServersStore.ts`) — already loaded at app startup via `useRagServersAutoLoad()`
- `<Select>` for the RAG server picker

**Verification**
- `docker exec ollama_frontend npx tsc --noEmit` clean
- `docker exec ollama_frontend npm run lint` zero warnings
- Manual: `/courses/new` with zero projects in DB but at least one RAG server shows the form and submits successfully

**Commit**: `feat(courses): standalone RAG — frontend form + types`

### Phase 7 — Frontend tests

**Files to modify**
- `frontend/src/components/courses/NewCourseForm.test.tsx`
  - Replace `useProjectsStore.setState(...)` with `useRagServersStore.setState({ servers: [...], loading: false, loaded: true, error: null })`
  - Update the "empty state" test: assert the "No RAG servers configured" message renders when `servers: []`
  - Update the submit-flow test to assert `createCourse` is called with `rag_server_id + rag_top_k` in the body (not `project_id`)
- `frontend/src/hooks/useCourseGeneration.test.tsx` — no change (no project reference)
- `frontend/src/components/courses/OutlineRenderer.test.tsx` — no change

**Verification**
- `docker exec ollama_frontend npm test -- --run` — all green (still 41 tests)

**Commit**: `test(courses): update frontend tests for standalone RAG`

### Phase 8 — End-to-end manual verification

No commit. User-driven against real Ollama + RAG corpus:
1. `psql` into Postgres, `DELETE FROM projects;` so the DB has no projects at all
2. Open `/rag-servers`, add a RAG server pointing at the Simple Wiki corpus
3. Open `/courses/new`, pick that RAG server, set `top_k=5`, fill the form, submit
4. Verify Research → Assembling → Done; outline renders; prerequisite chips navigate
5. Regenerate works; Delete works
6. If anything regresses, fix as separate `fix(courses): …` commits

## Verification (overall)

- `make migrate-up && make migrate-down && make migrate-up` clean
- `make test` green (backend, with 21+ course tests updated)
- `docker exec ollama_frontend npm test -- --run` green (frontend, 41+ tests)
- `docker exec ollama_frontend npx tsc --noEmit && docker exec ollama_frontend npm run lint` zero warnings
- Manual: a DB with zero projects but one RAG server can generate a course end-to-end

## Out of scope (explicit fast-follows)

- Optional `project_id` on Course for "organize this course under a project" UX. Reconsider if users ask.
- Inline "Add a RAG server" flow on the New Course page (instead of linking to `/rag-servers`).
- Bulk reassign-RAG-server for multiple courses at once.

## Files touched (summary)

Backend
- NEW: `backend/alembic/versions/<rev>_courses_drop_project_add_rag.py`
- `backend/app/db/models/course.py`
- `backend/app/schemas/course.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/course_service.py`
- `backend/app/api/v1/endpoints/courses.py`
- `backend/app/api/v1/endpoints/messages.py` (one call-site update)
- `backend/tests/test_api/test_courses.py`

Frontend
- `frontend/src/types/course.ts`
- `frontend/src/stores/courseStore.ts`
- `frontend/src/components/courses/NewCourseForm.tsx`
- `frontend/src/components/courses/NewCourseForm.test.tsx`
