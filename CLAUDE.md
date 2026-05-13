# Claude Code guide for ollama_gui_app

A self-hosted Ollama chat UI. FastAPI + React + Postgres in Docker; Ollama runs on the host.

## How to run it

- `make dev` — start dev environment with hot reload (Vite on :5173, FastAPI on :8000, Postgres on :5432)
- `make up` / `make down` — production-style up/down (no hot reload)
- `make clean` — stop services and delete the postgres volume
- `make logs` / `make logs-backend` / `make logs-frontend` — tail logs
- `make shell-db` — psql into the postgres container
- `make shell-backend` — bash into the backend container

Ollama must be running on the host (`ollama serve`) with at least one model pulled.

## Layout

```
backend/app/
  api/v1/endpoints/   chats, messages, models, projects, settings
  db/models/          SQLAlchemy 2 async ORM (Chat, Message, Project, ProjectFile, Settings, ChatSettings)
  schemas/            Pydantic v2 request/response schemas
  services/           ollama_service.py wraps the Ollama AsyncClient
  core/               config (Pydantic Settings), logging, exceptions
  main.py             FastAPI app + lifespan
  alembic/            migrations

frontend/src/
  components/         feature-grouped React components (chat/, projects/, sidebar/, files/, settings/, common/)
  contexts/           Context providers (Theme, Settings, Toast, View, Project, Chat) — being migrated to Zustand stores in PLAN_NEW.md Phase 5
  hooks/              useStreaming, useChats, useModels
  services/           per-resource axios layer + base api.ts
  types/              shared TS types
  styles/             global CSS + theme tokens

postgres/init.sql     legacy schema seed (being retired in PLAN_NEW.md Phase 2 — Alembic becomes the only source of truth)
docker-compose.yml
Makefile              entry point for all dev/ops commands
```

## Streaming

The chat stream is currently `GET /api/v1/chats/{id}/stream?message=...` consumed via `EventSource`. This is being replaced with `POST /api/v1/chats/{id}/stream` + `fetch` ReadableStream in `PLAN_NEW.md` Phase 4. Until that lands, the GET endpoint mutates the DB — yes, that's a known issue; the plan addresses it.

## Settings model

The `Settings` table is currently a single global row (`CHECK (id = 1)`). Env vars in `.env` are **seed values only** — they populate the row at first init, after which the DB is canonical. Don't expect changes to `DEFAULT_MODEL` env to propagate to an existing DB row. Edit via the AppSettings UI instead.

Phase 3 of `PLAN_NEW.md` makes settings per-user (drops the singleton).

## Tests + lint

- `make test` — backend pytest (40+ tests covering streams, isolation, file attachment, CRUD)
- `docker exec ollama_frontend npm test` — frontend Vitest (stores + useStreaming)
- `make lint` — ruff (backend) + eslint (frontend)
- `make format` — black (backend) + prettier (frontend)

CI (`.github/workflows/ci.yml`) runs all of the above on push + PR, plus
`alembic upgrade head`, `alembic check`, and a Docker image build.

### Pre-commit (optional but recommended)

```bash
pipx install pre-commit
pre-commit install
```

Then every `git commit` runs ruff + black on staged Python and eslint +
prettier on staged TS/CSS. Run on the whole tree with
`pre-commit run --all-files`.

## Migrations

- `make migrate message="your description"` — autogenerate a new revision
- `make migrate-up` — apply pending migrations
- `make migrate-down` — rollback the last migration

The initial migration `005bd22e40f1_initial_schema.py` is currently a no-op stub; real schema lives in `postgres/init.sql`. Phase 2 of `PLAN_NEW.md` backfills it.

## Refactor in progress

See `PLAN_NEW.md` at the project root for the approved multi-phase refactor (peer-reviewed). Phase 0 (hygiene + root-cause prep) is the current target.
