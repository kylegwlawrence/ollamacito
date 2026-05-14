# Claude Code guide for ollama_gui_app

A self-hosted Ollama chat UI. FastAPI + React + Postgres in Docker; Ollama runs on the host.

## How to run it

- `make dev` — start dev environment with hot reload (Vite on :5173, FastAPI on :8000, Postgres on :5432). Dev compose mounts source dirs so edits hot-reload.
- `make up` / `make down` — production-style up/down (no hot reload)
- `make clean` — stop services **and delete the postgres volume**
- `make logs` / `make logs-backend` / `make logs-frontend` / `make logs-db` — tail logs
- `make shell-db` — psql into the postgres container
- `make shell-backend` — bash into the backend container

Ollama must be running on the host (`ollama serve`) with at least one model pulled.

## Layout

```
backend/app/
  api/v1/endpoints/   chats, messages, models, projects, settings
                      get_current_user dep gates every user-scoped endpoint
  db/models/          SQLAlchemy 2 async ORM (User, Chat, Message, Project,
                      ProjectFile, Settings, ChatSettings; message_files junction)
  schemas/            Pydantic v2 request/response schemas
  services/           ollama_service.py wraps the Ollama AsyncClient
  core/               config (Pydantic Settings), logging, exceptions
  main.py             FastAPI app + lifespan (runs alembic upgrade head + seeds
                      default user + settings row on startup)
  alembic/            migrations (Alembic is the single source of truth)
  tests/test_api/     pytest suite — streaming, isolation, files, CRUD

frontend/src/
  components/         feature-grouped React components (chat/, projects/,
                      sidebar/, files/, settings/, common/)
  hooks/              useStreaming (POST + fetch ReadableStream + NDJSON),
                      useChats, useModels
  stores/             Zustand stores: toastStore, settingsStore, projectsStore,
                      chatStore. Each has *AutoLoad helper for hydration.
  services/           per-resource axios layer (api.ts) + streamApi.ts (raw fetch)
  router.tsx          React Router 7 routes — /, /chats/:chatId, /projects/:projectId,
                      /projects/:projectId/settings, /settings
  types/              shared TS types
  styles/             global CSS + theme tokens (dark only — set via <html data-theme>)
  test/               Vitest setup (jest-dom matchers)

docker-compose.yml + docker-compose.dev.yml   compose stack (override adds hot reload + Vite ports)
Makefile                                       entry point for dev/ops commands
PLAN_NEW.md                                    the refactor plan (mostly complete; see status below)
```

## Streaming

`POST /api/v1/chats/{id}/stream` with body `{content, file_ids: list[UUID] | null}`. Response is `application/x-ndjson` — one JSON object per `\n`-terminated line:

```
{"type":"chunk","content":"..."}
{"type":"done","truncated":false}
{"type":"error","message":"..."}
```

The endpoint commits the user message in its own transaction before invoking Ollama (so a stream failure doesn't lose what the user typed), polls `request.is_disconnected()` to handle client aborts, persists partial assistant messages with `truncated=true`, and fires title generation as an `asyncio.create_task` with its own DB session so it never blocks the `done` frame.

`file_ids` is the source of truth (no auto-fallback to "all project files"). Cross-project IDs are silently dropped. The selection is persisted to the `message_files` junction.

## State + routing (frontend)

- React Router 7 owns the URL → view mapping. There is no global `viewType`; the route renders the right page.
- Zustand stores replace the old Context providers. `useSettingsAutoLoad()` and `useProjectsAutoLoad()` are mounted from `App.tsx` to hydrate stores on first paint.
- `useStreaming` owns its own `isStreaming` / `streamingContent` state; the chat store does **not** mirror those. `onComplete` is captured via a ref so callers can pass inline closures without recreating the hook on every render.
- File-selection state lives in `chatStore.selectedFileIds`. `ChatContainer` resets it whenever the active chat changes; when the project has `auto_attach_all_files=true`, all files are pre-selected.

## Settings + users

Every user-scoped row carries a `user_id` FK. There is exactly one user today — the seeded default user with id `00000000-0000-0000-0000-000000000001` (constants in `app/db/models/user.py`). The migration that introduced multi-user schema also backfilled existing rows to that user.

`AUTH_ENABLED=false` (default): `get_current_user` returns the default user. The app is single-user. Flipping the flag to `true` currently raises `NotImplementedError` because the login flow (Phase 7) was deferred.

`Settings` is keyed by `user_id` (not the old `id=1` singleton). Env vars in `.env` are **seed values only** — they populate the row at first init, after which the DB is canonical. Don't expect a `DEFAULT_MODEL` env-var change to propagate to a running install; edit via the **Settings** view in the app instead.

## Migrations

- `make migrate message="your description"` — autogenerate a new revision
- `make migrate-up` — apply pending migrations
- `make migrate-down` — rollback the last migration

`alembic upgrade head` also runs on backend startup when `RUN_MIGRATIONS_ON_STARTUP=true` (default). Set it to `false` in prod to make migrations a deliberate deploy step.

## Tests + lint

- `make test` — backend pytest suite
- `docker exec ollama_frontend npm test` — frontend Vitest suite
- `make lint` — ruff (backend) + eslint (frontend)
- `make format` — black (backend) + prettier (frontend)

CI (`.github/workflows/ci.yml`) runs all of the above on push + PR, plus `alembic upgrade head`, `alembic check` (best-effort), `mypy` (best-effort), and a Docker image build. Path filters skip irrelevant job legs on PRs that only touch one side of the stack.

### Optional: pre-commit

`.pre-commit-config.yaml` wires ruff/black/eslint/prettier as staged-file hooks. Install with `brew install pre-commit` (or `pip3 install --user pre-commit`), then `pre-commit install`. Same checks run in CI either way.

## Refactor status (PLAN_NEW.md)

Done: Phase 0 (hygiene) · Phase 1 (stream correctness) · Phase 2 (Alembic single source of truth) · Phase 3 (auth scaffold + per-user schema) · Phase 4 (POST + NDJSON) · Phase 5 (Router + Zustand) · Phase 6 (selective file attachment) · Phase 8 (tests + CI).

Deferred: **Phase 7 (auth ON + rate limiting)** — the data model is multi-user-ready but the login flow / JWT / rate-limiter were skipped at the user's request. `AUTH_ENABLED=true` will raise until Phase 7 is done.

Explicitly out of scope (see PLAN_NEW.md §4): MCP, RAG/embeddings, memory generation, light mode (the `theme` field was removed), code-block syntax highlighting, OAuth, audit logging.
