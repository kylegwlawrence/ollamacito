# Code Review & Refactor Plan — Ollama GUI Chat App (Peer-Reviewed)

## Peer review log (vs. v1)

This is the second pass after a senior reviewer audit. Material changes:

- **Phase 3 fixed**: original "add `user_id` FK to settings" contradicted the singleton `CHECK (id = 1)`. Resolution: **per-user settings**; drop the singleton constraint and refactor lookups to `WHERE user_id = current_user.id`.
- **Two new latent bugs surfaced** and folded into Phase 1:
  - `ollama_service.py:128, 175` sends `options["num_ctx"] = max_tokens` — conflating *context window* (`num_ctx`) with *max generation tokens* (`num_predict`). They're different Ollama options. The Settings model already has a separate `num_ctx` column (added in migration `20260113_0000`) but the cascade in `messages.py:260–280` ignores it and stuffs `max_tokens` into `num_ctx` anyway. Both fields should be honored correctly.
  - `ollama_service.py:265` reads `settings.title_generation_model` (env-var) for title gen, but the Settings table now stores a user-editable `conversation_summarization_model` column (added in the same migration). The UI lets users change it (`AppSettings.tsx:53`); the value is ignored at runtime.
- **`check_and_update_settings.py` is a symptom-fix, not a debug script** — it patches the env-var-vs-DB-default drift for `default_model`. Phase 0 now addresses the **root cause**: Settings row is seeded once from env vars at first init; after that, DB is canonical. The standalone script gets deleted along with the design problem.
- **Phase 6 file-attachment default**: user chose "migrate everyone to selective". Migration backfills `auto_attach_all_files=false` for **all** existing projects. Selective is the new default everywhere.
- **Light mode is dropped**, not deferred — Phase 0 strips the unused `theme` field from the Settings model + a migration removes the column. Original spec called for both, but the half-built scaffolding is more confusing than valuable; add back deliberately later if wanted.
- **Auth library: hand-roll JWT** — `passlib[bcrypt]` + `python-jose`, ~150 lines for signup/login/JWT-cookie/`get_current_user`. No `fastapi-users`.
- **TimestampMixin already implements `onupdate`** (`backend/app/db/base.py:24–28`) — Phase 2's "port the trigger to ORM" is mostly free; just drop the SQL trigger from the backfilled migration.
- **Duplicate `get_db`** exists in both `backend/app/db/session.py` (bottom) and `backend/app/api/deps.py:14`. The session.py copy is dead code — endpoints import from `deps`. Folded into Phase 0.
- **Phase 4 simplified**: no "deprecation period" for GET stream endpoint — personal app, no release cadence; remove cleanly in the same PR.
- **Coverage gate softened**: 70% backend, 50% frontend (UI tests have lower ROI per LOC than service/route tests).
- **Explicit "Out of scope"** section added (MCP server, RAG, memory generation, light mode, code-block syntax highlighting — all defer to follow-up work).
- **Streaming abort**: explicit decision to **persist partial assistant message** with a new `truncated: bool` column on `Message`. UI can offer "regenerate" later. Adds a migration in Phase 1.

---

## Context

A personal Ollama chat UI built haphazardly over time. The user wants it polished into a maintainable, transferable codebase that can scale to multi-user / shared deployment. The foundation is **better than expected** — feature-folder layout is sound, TypeScript is strict, Pydantic v2 + async SQLAlchemy 2 are modern. But there are real correctness bugs in the streaming path, schema has two competing sources of truth, six nested context providers obscure state ownership, and structural debt has accumulated.

User decisions driving this plan:
- Eventually multi-user / shared deployment → scaffold auth now, flip on later
- Switch streaming `GET ?message=` + EventSource → `POST` + `fetch` ReadableStream
- Replace `ViewContext` + 6 nested Context providers with **React Router + Zustand**
- Switch file context from "auto-attach all" → **selective per-message attachment** (no preservation of old behavior; all projects migrate to selective)
- **Per-user settings** (drop singleton constraint)
- **Hand-roll JWT** auth (no `fastapi-users`)
- **Light mode dropped** (strip the unused scaffolding)
- **Comprehensive tests**: 70% backend, 50% frontend, written alongside each phase

---

## 1. Review — Critical findings (confirmed)

### Backend correctness
- **Silent user-message data loss** — `backend/app/api/v1/endpoints/messages.py:387–393` flushes the user `Message` mid-stream but only commits at line 421; on any error between, the implicit rollback at `session.close()` (line 457) drops the user's message. Optimistic UI shows it, then it vanishes on refresh.
- **Title generation blocks the `done` signal** — `messages.py:435` runs synchronously before `messages.py:440`. FE sees a 1–3s delay after the stream finishes.
- **`GET /stream?message=...` mutates DB** — `messages.py:196–201`. User content in URL → proxy logs / browser history; URL ~8 KB cap contradicts `max_length=32000`; violates HTTP semantics.
- **Auto-attach-all-project-files every turn** — `messages.py:306–345`. Linear-cost-in-files context bloat.
- **NEW: `num_ctx` and `max_tokens` are conflated** — `ollama_service.py:128, 175` sends `max_tokens` as `num_ctx` (context window) when it should be `num_predict` (generation cap). The Settings model has both columns; the cascade in `messages.py:260–280` only honors `max_tokens`. Both Ollama options should be set independently.
- **NEW: `conversation_summarization_model` DB column is ignored** — `ollama_service.py:265` uses `settings.title_generation_model` (env var) instead of the DB column. UI lets users change it; runtime ignores them.
- **NEW: Duplicate `get_db`** — `backend/app/db/session.py` (bottom) and `backend/app/api/deps.py:14`. The session.py copy is dead.

### Frontend correctness
- **`useStreaming` leaks EventSource on unmount** — `frontend/src/hooks/useStreaming.ts:19–88`; no cleanup `useEffect`.
- **Race on rapid re-send** — `useStreaming.ts:38` overwrites `eventSourceRef.current` without closing the previous one.
- **Silent partial-response acceptance** — `useStreaming.ts:69–80`: on `onerror`, a truncated stream is persisted as if it completed.
- **Hook re-creates every render** — `ChatContainer.tsx:15–20` passes a new inline `onComplete` per render.
- **TDZ-adjacent bug** — `ChatContainer.tsx:46` references `projectFiles` before its declaration on line 65.
- **Dead `ChatContext` state** — `frontend/src/contexts/ChatContext.tsx` exposes `isStreaming`/`streamingContent`/setters that nothing reads.
- **`ProjectDetail.tsx`** (470 lines) — four sequential form-sync `useEffect`s; a `<div onClick>` (a11y miss).
- **`Sidebar.tsx:75`** — `window.prompt()` for project creation (a11y + UX miss).

### Architecture
- **Two schema sources of truth** — `postgres/init.sql` (real) + empty Alembic initial migration. Three follow-ups on top.
- **Six nested Context providers + custom `ViewContext`** — no URL state, no deep links, refresh loses you.
- **`message_files` junction table defined but unused for writes** — will be activated in Phase 6.
- **`chats_with_stats` view in `init.sql` is unreferenced** — confirmed dead.
- **Singleton `Settings` row** — `CHECK (id = 1)` (`settings.py:53`); incompatible with per-user requirement.
- **No auth despite `secret_key` validator** — `config.py:73–79` enforces it when `DEBUG=false` but nothing uses it.

### Structure & hygiene
- **`.DS_Store` committed** at three paths, not in `.gitignore`.
- **Loose backend scripts** — `init_db.py`, `check_and_update_settings.py`, `test_file_context.py`.
- **Empty test directories** — all `__init__.py` are 0 bytes. No frontend tests, no CI.
- **Three logo PNGs**, only `green_logo_3.png` referenced.
- **Doc drift** — `README` says `qwen2.5-coder:14b`; `config.py` says `mistral:7b`; `init.sql` says `qwen2.5-coder:14b`.
- **No CLAUDE.md**.

### Strengths to preserve
- Feature-folder layout in both backend `endpoints/` and frontend `components/`
- Strict TypeScript, no `any`
- Async SQLAlchemy 2 + Pydantic v2
- Cascading settings logic (chat → project → global → default) at `messages.py:260–280` (modulo the `num_ctx`/`max_tokens` bug)
- FastAPI exception handlers at `app/main.py:82–120`
- `TimestampMixin` already has `onupdate=lambda: datetime.now(timezone.utc)` (`base.py:24–28`) — Phase 2 work is mostly free
- `ErrorBoundary` wrapping per view in `MainContent.tsx`
- Per-resource thin axios layer; uniform `getErrorMessage` utility
- Docker compose + Makefile

---

## 2. Sequencing principle

Lowest-risk first, foundation early, behavior-changing last. Auth scaffolding lands **before** Zustand/Router so the new stores don't have to be re-keyed by `user_id` later. Tests are written **within each phase**, not in a separate final pass. Each phase = one shippable PR (or a small series).

---

## 3. Implementation Plan

### Phase 0 — Hygiene & root-cause prep (zero behavioral risk)
**Goal**: clean tree; resolve underlying confusions so later phases have a stable base.

- Add `.DS_Store`, `**/.DS_Store`, `*.tmp` to `.gitignore`; `git rm --cached` tracked `.DS_Store` files
- Delete `frontend/public/green_logo_2.png`, `green_logo_fixed.png` (verify CSS first)
- Delete `backend/test_file_context.py`, `backend/init_db.py`
- **Delete `backend/check_and_update_settings.py` AND fix the root cause**: remove `lambda: app_settings.default_model` / `lambda: app_settings.title_generation_model` defaults from `Settings` model. Replace with literal column defaults (`server_default="mistral:7b"` etc.). DB becomes the only source of truth after first init; env vars are seed-only at install time, documented as such
- **Remove duplicate `get_db`** from `backend/app/db/session.py` (keep the one in `deps.py`)
- Reconcile default model — pick one canonical (e.g. `qwen2.5-coder:14b`) across `config.py`, `docker-compose.yml`, `README.md`, `init.sql`. This is the seed only; users can change via UI
- Fix `ChatContainer.tsx:43–67` — move `projectFiles` const above `handleSend`
- Add `CLAUDE.md` documenting dev workflow, layout, test commands
- Move `project_prompt.md` → `docs/project_prompt.md`

**Files**: `.gitignore`, `README.md`, `backend/app/core/config.py`, `backend/app/db/models/settings.py`, `backend/app/db/session.py`, `docker-compose.yml`, `postgres/init.sql`, `frontend/src/components/chat/ChatContainer.tsx`, deletions listed above, `CLAUDE.md` (new), `docs/project_prompt.md` (move).

### Phase 1 — Backend stream correctness (+ surfaced bugs)
**Goal**: stop losing user messages on stream failure; unblock the `done` signal; support client abort; fix two latent bugs.

- In `messages.py` `stream_chat_response`:
  - **Commit the user message immediately in its own transaction** (`AsyncSessionLocal()` opened, user `Message` added, committed, closed) before invoking Ollama
  - On stream success, save the assistant message in a second transaction
  - **Detect client abort**: take `request: Request`, poll `await request.is_disconnected()` inside the stream loop. On disconnect, cancel the Ollama generator and **persist the partial assistant message with `truncated=True`** (new column — adds a small migration in this phase)
  - **Move title generation off the request path**: `asyncio.create_task(generate_and_update_title(chat_id))` where the task opens its own `AsyncSessionLocal()`. Yield `done` immediately after the assistant save
- In `ollama_service.py`:
  - `stream_chat`: ensure the async generator is closed on cancellation (`try/finally: await stream.aclose()`)
  - **Fix `num_ctx` / `num_predict` conflation**: `chat()` and `stream_chat()` should accept both `max_tokens` (→ `options["num_predict"]`) and `num_ctx` (→ `options["num_ctx"]`) explicitly. Update the cascade in `messages.py:260–280` to compute both from Settings/Project/ChatSettings independently
  - **Fix `_load_title_prompt` / model**: `generate_chat_title` should accept the model name as a parameter; the streaming endpoint reads `settings.conversation_summarization_model` from the DB and passes it in. Env var becomes the seed only
- Add a migration: new `Message.truncated` column (nullable bool defaulting to `false`)
- Add `pytest` tests for the streaming endpoint: happy path, Ollama-down, client disconnect mid-stream, title generation races stream end, `num_ctx`/`num_predict` flow correctly through to Ollama

**Files**: `backend/app/api/v1/endpoints/messages.py`, `backend/app/services/ollama_service.py`, `backend/app/db/models/chat.py` (Message gains `truncated`), `backend/app/schemas/message.py`, `backend/alembic/versions/` (new migration), `backend/tests/test_api/test_messages.py` (new), `backend/tests/conftest.py` (new — pytest-asyncio, test DB, Ollama mock).

### Phase 2 — Schema: Alembic as single source of truth
**Goal**: kill `postgres/init.sql`; Alembic authoritative; existing dev DBs survive.

- **Backfill `005bd22e40f1_initial_schema.py`** with `op.create_table(...)` calls matching the schema as it existed at that revision. Excludes:
  - The `update_updated_at_column` trigger (ORM `onupdate` already handles it — `base.py:24–28` confirms)
  - The `chats_with_stats` view (unused)
- **Drop the `theme` field from the `Settings` table** in a new migration: light mode is out of scope
- Generate via `alembic revision --autogenerate` against an empty DB; hand-edit to ensure deterministic column order / index naming
- **Remove `init.sql` mount** from `docker-compose.yml:13`; delete `postgres/init.sql`
- **Startup migration**: in `backend/app/main.py` lifespan, run `command.upgrade(alembic_cfg, "head")` (env-flagged `RUN_MIGRATIONS_ON_STARTUP=true` default; flip to `false` in prod for manual control)
- **Seed Settings row in lifespan** if missing (one-time, idempotent)
- **Upgrade-path doc**: existing DBs run `alembic stamp 005bd22e40f1` once → subsequent `upgrade head` runs migrations 2–4 + Phase 1's `truncated` + Phase 2's `theme` drop

**Files**: `backend/alembic/versions/005bd22e40f1_initial_schema.py` (backfill), `backend/alembic/versions/` (new migration: drop `theme`), `backend/app/db/models/settings.py` (remove `theme` field + constraint), `backend/app/main.py` (alembic upgrade + seed Settings), `docker-compose.yml`, `postgres/init.sql` (delete), README upgrade note, `backend/tests/test_db/test_migrations.py` (new — alembic upgrade head + `alembic check`).

### Phase 3 — Auth scaffold (per-user settings, no UI yet)
**Goal**: ship the FK shape and `get_current_user` shim so later phases don't double-touch every file.

- New `User` model — `backend/app/db/models/user.py` (id UUID, email unique, hashed_password, created_at, is_active). Hand-roll shape: no `fastapi-users` mixins.
- Migration adding `user_id` FK to `chats`, `projects`. **Drop the singleton constraint on `settings`** and add `user_id` as a NOT NULL FK (after backfill)
- Migration backfill: insert a seeded "default user" with a stable UUID baked into the migration; backfill all existing `chats.user_id`, `projects.user_id`. For `settings`: change the single existing row's `id` semantics — make `user_id` PK, delete the singleton `id=1` row, insert a fresh per-user row for the default user from the env-var seeds. Update all endpoint queries from `WHERE id = 1` → `WHERE user_id = current_user.id`
- New config flag `AUTH_ENABLED: bool = False` in `backend/app/core/config.py`
- `backend/app/api/deps.py`: `get_current_user()` — when `AUTH_ENABLED=false`, returns the seeded default user (cached); when `true`, validates JWT cookie (implementation lands in Phase 7, raises `NotImplementedError` here until then)
- Apply `Depends(get_current_user)` to every endpoint touching user-scoped data: chats, messages, projects, files, settings
- All queries filter `WHERE user_id = current_user.id` (or via FK traversal: `Chat.project.user_id == ...`)
- Update the `auto-attach all files` query in `messages.py:306–345` to filter `ProjectFile` by project ownership (defense in depth; the FK already constrains it)

**Files**: `backend/app/db/models/user.py` (new), `backend/app/db/models/__init__.py`, `backend/app/db/models/{chat,project,settings}.py`, `backend/app/api/deps.py`, `backend/app/core/config.py`, `backend/alembic/versions/` (new migration), all endpoint files (deps + query filters), `backend/tests/test_api/test_user_isolation.py` (new — verifies default user behavior with auth off; flipping to true raises until Phase 7).

### Phase 4 — POST streaming transport
**Goal**: replace `GET ?message=` + EventSource with `POST` + `fetch` ReadableStream. NDJSON framing. **Remove the GET endpoint cleanly** — no deprecation period.

- **Backend**: new `POST /api/v1/chats/{id}/stream` endpoint. Body: `{ content: str, file_ids: list[UUID] | null }` (file_ids is the hook for Phase 6; null falls back to current "all project files" until Phase 6 lands, then `null` means none). NDJSON response: one JSON per line: `{"type":"chunk","content":"..."}`, `{"type":"done"}`, `{"type":"error","message":"..."}`. Keep `X-Accel-Buffering: no`
- **Delete the GET stream endpoint** in the same PR
- **Frontend**: new `frontend/src/services/streamApi.ts` (raw `fetch` for ReadableStream support; share base URL + credentials with `api.ts`)
- Rewrite `useStreaming.ts`:
  - `useRef<AbortController>` instead of `useRef<EventSource>`
  - `useEffect` cleanup: `controller.abort()` on unmount
  - **Reject** re-entry while streaming (don't queue) — input UI is already disabled via `disabled={streaming.isStreaming}` in `ChatContainer.tsx:112`
  - On error, **always** surface to caller; never accept a partial response as "done"
  - Stabilize `onComplete` via ref pattern (set in a `useEffect`, read inside `sendMessage`) so inline callers don't recreate the hook every render
  - Handle the new `truncated` flag from the assistant message metadata
- Vitest + MSW tests for the hook
- **React 18 Strict Mode mitigation**: use a mount-id ref so the dev-mode double-mount doesn't abort the first stream

**Files**: `backend/app/api/v1/endpoints/messages.py`, `frontend/src/hooks/useStreaming.ts`, `frontend/src/services/streamApi.ts` (new), `frontend/src/services/messageApi.ts`, `frontend/src/components/chat/ChatContainer.tsx`, `backend/tests/test_api/test_stream_post.py` (new), `frontend/src/hooks/useStreaming.test.tsx` (new).

### Phase 5 — Router + Zustand (incremental, one slice per PR)
**Goal**: real URL routing; one Zustand store replacing the 6 Context providers.

- **Add `react-router-dom`** with routes: `/` (latest chat or empty), `/chats/:chatId`, `/projects/:projectId`, `/projects/:projectId/settings`, `/settings`. Each route gets its own `<ErrorBoundary onReset={...}>` wrapper — preserves the pattern from `MainContent.tsx:11–42`. Delete `ViewContext.tsx` and `MainContent.tsx` (routes own the dispatch)
- **Add `zustand`**. Create `frontend/src/stores/`. Migrate one Context slice at a time; delete each Context file after consumers switch:
  1. `ToastContext` → `toastStore` (leaf)
  2. `ThemeContext` → **delete entirely** (light mode dropped in Phase 2; UI is dark-only; one-line `<html data-theme="dark">` in `index.html`)
  3. `SettingsContext` → `settingsStore`
  4. `ProjectContext` → `projectsSlice` + `currentProjectSlice`
  5. `ChatContext` → `chatStore`. **Drop the dead `isStreaming`/`streamingContent` fields** during the migration; `useStreaming` keeps owning that state

**Files**: `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/components/MainContent.tsx` (delete), `frontend/src/contexts/{Theme,View,...}Context.tsx` (delete after each slice migrates), `frontend/src/stores/*.ts` (new), `frontend/src/router.tsx` (new), `frontend/index.html` (data-theme=dark static), consumers of each Context, `frontend/src/stores/*.test.ts` (new).

### Phase 6 — Selective per-message file attachment
**Goal**: stop force-bloating context with all project files; activate the dormant `message_files` junction.

- **Frontend** `MessageInput.tsx`: file chip selector showing all project files; user picks per message. Selection lives in `chatStore` (so it survives focus changes within the chat). After Phase 5
- **Backend** `messages.py` stream endpoint: read `file_ids` from POST body. Treat as the source of truth — **no fallback to "all files"** (user chose "migrate everyone to selective"). Insert into `message_files` junction in the same transaction as the user message
- Add `auto_attach_all_files: bool` to `Project` (column + migration). Default `false` for ALL projects (existing + new) per the user's "migrate everyone to selective" choice. UI exposes the toggle in `ProjectDetail.tsx`. When `true`, the FE pre-selects all files on each new message (user can still deselect)
- The auto-attach-all code path at `messages.py:306–345` is gone — replaced by reading the request's `file_ids`
- Migrate the system-prompt builder to include only selected files

**Files**: `frontend/src/components/chat/MessageInput.tsx`, `frontend/src/components/chat/ChatContainer.tsx`, `frontend/src/components/projects/ProjectDetail.tsx`, `frontend/src/stores/chatStore.ts`, `backend/app/api/v1/endpoints/messages.py`, `backend/app/schemas/message.py`, `backend/app/db/models/project.py` (add `auto_attach_all_files`), `backend/alembic/versions/` (new migration), tests.

### Phase 7 — Auth ON + rate limiting (hand-rolled)
**Goal**: implement the auth shim from Phase 3; flip the switch.

- Hand-roll auth in `backend/app/api/v1/endpoints/auth.py`:
  - `POST /auth/signup` — `passlib[bcrypt]` hashes, creates `User` row, returns session cookie
  - `POST /auth/login` — verify password, mint JWT (`python-jose`), set as httpOnly cookie
  - `POST /auth/logout` — clear cookie
  - `get_current_user` (in `deps.py`) when `AUTH_ENABLED=true`: read JWT cookie, verify signature/expiry, return `User`
- Cookie config: `httpOnly=True, samesite="strict", secure=settings.cookie_secure` where `cookie_secure` defaults to `not settings.debug` (true in prod, false on localhost). Documented: cross-domain deployments require explicit reconfiguration
- CSRF: `SameSite=Strict` + same-origin assumption (frontend + API on the same domain in production). Document this constraint in DEPLOYMENT.md. If split-domain is needed, that's a follow-up
- Frontend `/login` + `/signup` routes; `<RequireAuth>` wrapper that no-ops when `AUTH_ENABLED=false` (queries `/auth/me` to check)
- Migrate the seeded default user into a real account: documented manual step (`make migrate-default-user EMAIL=... PASSWORD=...`)
- **Rate limiting** with `slowapi`, keyed by `current_user.id`:
  - `/auth/signup`, `/auth/login`: 5/min/IP (IP-based for unauth'd endpoints)
  - `POST /chats/{id}/stream`: 10/min/user (per-user keyed)
  - Global: 200/min/user
- **Enforce `secret_key` non-empty unconditionally** when `AUTH_ENABLED=true` (currently only enforced when `DEBUG=false`)
- Tighten CORS to specific origins; document HTTPS reverse-proxy requirement

**Files**: `frontend/src/routes/{login,signup}.tsx` (new), `frontend/src/components/RequireAuth.tsx` (new), `backend/app/api/v1/endpoints/auth.py` (new), `backend/app/api/deps.py` (real JWT validation), `backend/app/main.py` (slowapi middleware), `backend/app/core/config.py` (cookie_secure flag), `backend/requirements.txt` (passlib, python-jose, slowapi), README/DEPLOYMENT.md updates.

### Phase 8 — Tests + CI (raise floor; most coverage added in earlier phases)
**Goal**: fill gaps and gate with CI.

- Backend: fill in tests for projects, files, settings, chats endpoints (areas not touched by Phases 1–7)
- Frontend: Vitest + `@testing-library/react` + MSW for the stores, hooks, and key components (MessageList, ProjectDetail, Sidebar, MessageInput)
- **GitHub Actions** at `.github/workflows/ci.yml`:
  - `backend-test`: ruff + black --check + mypy + pytest with coverage; postgres service container; alembic `upgrade head` + `check`
  - `frontend-test`: eslint + `tsc --noEmit` + vitest
  - `docker-build`: build (not push) on PR; push to GHCR on `main`
  - Path filters; concurrency cancel-in-progress
  - **Coverage gate**: 70% backend, 50% frontend (lowered from initial 70/70 — frontend tests have lower ROI per line; revisit later)
- **Pre-commit** (`.pre-commit-config.yaml`): ruff, black, eslint, prettier, alembic check, lint-staged for staged-files only
- **Hadolint** on Dockerfiles; `pip-audit` + `npm audit` for vuln scanning

**Files**: `.github/workflows/ci.yml` (new), `.pre-commit-config.yaml` (new), `frontend/vitest.config.ts` (new), `frontend/package.json` (devDeps: vitest, @testing-library/react, jsdom, msw), `backend/tests/**` (populate), `frontend/src/**.test.{ts,tsx}` (populate).

---

## 4. Out of scope (explicit non-goals)

- **MCP server integration** (from `todo.md`) — defer
- **RAG / embeddings / retrieval** (from `todo.md`) — selective file attachment is the chosen scaling path for now
- **Memory generation** (from README "coming soon") — defer
- **Light mode** — schema scaffolding stripped; add back deliberately if/when wanted
- **Code-block syntax highlighting** (from `todo.md`) — defer; `react-markdown` v9's HTML disable already handles XSS
- **Move standalone chat between projects** (from `todo.md`) — defer
- **Multi-domain (FE + API on different origins) deployment** — same-origin assumed; cross-domain CSRF is a follow-up
- **OAuth / social login / email verification / password reset** — hand-rolled JWT only; add when needed
- **Rate limiting beyond basic per-user quotas** — no abuse-detection / IP blocking / WAF
- **Audit log table for auth events** — useful later; not now
- **Removing `lazy="selectin"` from `Chat.messages`** — performance trap at scale, note for follow-up

---

## 5. What NOT to touch

- `OllamaService` singleton structure (`backend/app/services/ollama_service.py`) — only fix the `num_ctx`/`num_predict` and prompt-loading bugs
- FastAPI exception handlers (`backend/app/main.py:82–120`, `app/utils/exceptions.py`)
- Pydantic v2 schemas under `backend/app/schemas/` (only add fields as needed by features)
- Feature-folder layouts on backend + frontend
- `TimestampMixin` / `Base` — already correct; just rely on it more in Phase 2
- Alembic migrations 2/3/4 — only the empty initial migration gets backfilled
- `pyproject.toml` tool config (ruff/black/mypy already configured)
- `Dockerfile.dev` vs `Dockerfile` split

---

## 6. Risks to manage

- **Existing dev DBs** at Phase 2 merge: backfilled migration would try to re-create tables. Mitigation: `alembic stamp 005bd22e40f1` in upgrade notes; automated as a `make stamp-existing` target. Test on a copy of the current DB.
- **BackgroundTasks vs session**: title gen via `asyncio.create_task` must open its **own** `AsyncSessionLocal()`; never capture the request-scoped session
- **Phase 3 user_id NOT NULL FK**: cannot add NOT NULL to a non-empty table without `server_default`. Pattern: add column nullable → backfill → `ALTER COLUMN SET NOT NULL` in same migration
- **Phase 3 settings refactor**: changing PK and dropping a `CHECK` constraint on a live table — sequence as nullable add, backfill, swap PK, drop old constraint. Test on a copy
- **React 18 Strict Mode + `AbortController`**: dev double-mount aborts the first stream. Use a mount-id ref to ignore aborts from the first mount
- **Zustand persist hydration is async** — for stores that persist (e.g. selected model in `chatStore`), gate first render. (Theme is no longer persisted; dropped.)
- **POST body buffering proxies**: corporate proxies may buffer POST bodies. Document the constraint
- **Selective files breaks UX abruptly** (per user's choice): users open chats and see no files attached by default. **Mitigation**: clearly label the new file selector, show the project files visibly, surface the per-project `auto_attach_all_files` toggle prominently
- **Removing `init.sql` breaks fresh Docker volumes**: Phase 2's startup migration must run before the app accepts traffic. Backend healthcheck should depend on alembic completion
- **Cookie `Secure` on localhost dev**: must be conditional (`cookie_secure = not settings.debug`) or login fails over HTTP
- **`message_files` cascade**: junction has `ON DELETE CASCADE` on both FKs (`chat.py:18–19`). When a `ProjectFile` is deleted, its message references go too. Verify this is desired (it is — orphaned junction rows would be worse)
- **Title generation as `asyncio.create_task`** — if the uvicorn worker dies, the task dies. Acceptable for personal use; revisit if it becomes critical

---

## 7. Verification

Each phase is a discrete shippable PR series; merge gates listed:

- **Phase 0**: `git status` clean of `.DS_Store`; `make dev` boots; one happy chat round-trip; `default_model` in DB matches env var on fresh init; updating it in the UI does not get clobbered on restart
- **Phase 1**: `docker kill ollama_chat_backend` mid-stream → restart → user message still in DB (`make shell-db`); send a new message → `done` arrives ≤200ms after final token; client disconnect mid-stream → backend logs detect it, `Message.truncated=true` row inserted; tests verify `num_ctx` and `num_predict` reach Ollama independently with correct values; tests verify `conversation_summarization_model` from DB is honored
- **Phase 2**: `docker-compose down -v && make dev` boots cleanly with no `init.sql`; `alembic check` reports no diff; migration tests green; `theme` column gone from `settings`
- **Phase 3**: every endpoint requires `Depends(get_current_user)`; with `AUTH_ENABLED=false`, all existing rows belong to the default user; `WHERE user_id` filtering present in all queries; pgsql constraint on `settings.user_id` not null; flipping `AUTH_ENABLED=true` raises `NotImplementedError` (Phase 7 fills it)
- **Phase 4**: `curl --no-buffer -X POST -H 'Content-Type: application/json' -d '{"content":"hi"}'` against `/chats/{id}/stream` streams NDJSON; FE chat works; navigate away mid-stream → backend logs detect disconnect, partial message persisted with `truncated=true`; rapid double-send → second rejected, no leak; old GET endpoint returns 404; Vitest hook suite green
- **Phase 5**: deep-link `/projects/{id}/settings` works on fresh load; browser back/forward works; all six former contexts deleted from `/contexts`; each route has its own ErrorBoundary; data-theme=dark static in index.html
- **Phase 6**: project with 3 files, send message with 1 selected → backend logs show only that file in prompt; `message_files` rows created in same TX as user message; toggle `auto_attach_all_files=true` → new messages pre-select all files; previously-sent messages retain their attached file set
- **Phase 7**: with `AUTH_ENABLED=true`, signup → login → cookie issued → streams work; hammering `/stream` trips rate limit (10/min); login from a second user → completely isolated data; cookie `Secure` true in prod, false in dev
- **Phase 8**: CI green on main; coverage ≥70% backend, ≥50% frontend; pre-commit hooks pass locally

**End-to-end smoke after Phase 7** (clean environment):
1. `docker-compose down -v && cp .env.example .env && make dev`
2. Wait for backend health check (alembic completes before /health)
3. Sign up at `/signup` → land on `/`
4. Create a project; upload two small text files
5. Create a chat inside it; **select one file**; send "summarize file A" → assistant streams a relevant answer
6. `docker compose kill backend` mid-stream → `docker compose start backend` → user message preserved, partial assistant message marked `truncated=true` and visible in history
7. Sign out; sign in; data still there; switch to a second user → only their data is visible
8. Try to access first user's chat by direct URL `/chats/{id}` → 404

---

## 8. Critical files

- `backend/app/api/v1/endpoints/messages.py` — streaming, title generation, file context (Phases 1, 4, 6)
- `backend/app/services/ollama_service.py` — `num_ctx`/`num_predict` fix, title model fix (Phase 1)
- `backend/app/db/models/settings.py` — drop `theme`, drop singleton, add `user_id` (Phases 0, 2, 3)
- `frontend/src/hooks/useStreaming.ts` — leaks, races, partial-response acceptance (Phase 4)
- `backend/alembic/versions/005bd22e40f1_initial_schema.py` — empty stub; backfill (Phase 2)
- `frontend/src/App.tsx` + `frontend/src/components/MainContent.tsx` — Context nesting + view switch (Phase 5)
- `backend/app/db/models/{chat,project,user}.py` — `user_id` FKs + new User model (Phase 3)
- `backend/app/api/deps.py` — `get_current_user`; remove duplicate `get_db` from `session.py` (Phases 0, 3, 7)
- `frontend/src/components/chat/ChatContainer.tsx` — TDZ fix + selective files wiring (Phases 0, 6)
- `.github/workflows/ci.yml` — referenced by every prior phase's "green" gate (Phase 8)
