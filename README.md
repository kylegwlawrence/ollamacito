# Ollama Chat

A web chat application for interacting with locally-installed Ollama models. FastAPI + React + Postgres in Docker; Ollama runs on the host.

## Features

- **Projects**: organize related chats; give each project its own custom system instructions and a per-project default model
- **Per-message file attachment**: upload `txt`/`json`/`csv`/`md` files to a project, then pick exactly which files to attach to each message. Per-project toggle to pre-select all on every new turn.
- **Streaming responses** over `POST` + NDJSON with mid-stream stop support. Partial responses are persisted with a `truncated` flag if the stream is aborted or fails.
- **Auto-generated chat titles** after the first assistant response (runs as a background task; does not block the stream).
- **Cascading model settings**: per-chat → per-project → global → hardcoded fallback.
- **URL-driven navigation**: refresh, back/forward, and deep-links all work.
- **Multi-user-ready data model**: every row is scoped by `user_id`; login UI is not enabled by default (single-user mode), but the schema and request pipeline are ready for it.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Ollama](https://ollama.ai/) running locally with at least one model installed (`ollama pull mistral:7b` works as a small starter model)
- ~4 GB free RAM (the model is what's heavy; the app itself is small)

## Quick Start

1. Clone the repo and `cd` into it.
2. `cp .env.example .env` and set at least `POSTGRES_PASSWORD`.
3. `make dev` — starts Postgres + FastAPI (hot reload) + Vite dev server.
4. Open <http://localhost:5173>. API docs at <http://localhost:8000/docs>.

`make clean && make dev` wipes the database and starts fresh.

## Configuration

`.env` (copy from `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_PASSWORD` | Database password | **required** |
| `POSTGRES_USER` / `POSTGRES_DB` | Database user / name | `postgres` / `ollama_chat` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://host.docker.internal:11434` |
| `DEFAULT_MODEL` | Seed value for new installs' default chat model | `qwen2.5-coder:14b` |
| `DEBUG` | Debug mode (verbose logs, no SECRET_KEY check) | `true` |
| `RUN_MIGRATIONS_ON_STARTUP` | Apply `alembic upgrade head` in the FastAPI lifespan | `true` |
| `AUTH_ENABLED` | Reserved; flipping to `true` currently raises (login flow not yet shipped) | `false` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173,...` (includes `127.0.0.1` variants) |

**`DEFAULT_MODEL` and friends are seed values only.** On first init the backend writes them into the per-user `settings` row in the database; after that, the database is canonical. Edit your defaults in the **Settings** view inside the app — changing the env var on a running install will not update existing rows.

## Available commands

```bash
make dev          # development stack with hot reload
make up           # production-style stack (no hot reload)
make down         # stop everything
make clean        # stop + delete the postgres volume (wipes data)
make test         # backend pytest suite
make logs         # tail all container logs
make shell-db     # psql into the postgres container
make migrate-up   # apply pending migrations manually (also runs on startup)

docker exec ollama_frontend npm test    # frontend Vitest suite
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│     Backend     │────▶│   PostgreSQL    │
│  React + Vite   │     │     FastAPI     │     │       16        │
│   Port 5173     │     │   Port 8000     │     │   Port 5432     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │     Ollama      │
                        │  (host machine) │
                        │   Port 11434    │
                        └─────────────────┘
```

Frontend uses React Router for navigation and Zustand for state. Streaming is POST + `fetch` ReadableStream with NDJSON framing — one JSON object per `\n`-terminated line: `{"type":"chunk","content":"..."}`, `{"type":"done","truncated":bool}`, or `{"type":"error","message":"..."}`.

## Usage

### Projects
1. Click **"+ Create Project"** in the sidebar.
2. In the project view, expand **Project Settings** to add custom instructions and project-level defaults (model, temperature, max tokens).
3. Upload files (`txt`/`json`/`csv`/`md`) — they show up in the per-message attach picker inside any chat in this project.
4. Tick **"Auto-attach all project files to new messages"** if you want every new message to pre-select all files (you can still deselect any before sending).
5. Deleting a project cascade-deletes its chats and files.

### Chats
- **Standalone chats** are created from the sidebar's **"+ New Chat"** button.
- **Project chats** are created from inside the project view.
- Each chat has its own model selector and supports per-chat overrides for temperature / max tokens.

### Per-message file attachment
Inside a project chat, the message input shows a chip for every project file. Click to attach/detach. Empty selection = no files attached to that turn. The chat history records which files were attached to each user message.

### Keyboard shortcuts
- `Enter` — send message
- `Shift + Enter` — new line
- `Tab` — navigate interactive elements
- `Escape` — cancel rename

## Testing

- **Backend** (pytest): `make test` — covers streaming correctness, per-user isolation, selective file attachment, CRUD for chats/projects/files/settings, Ollama model listing.
- **Frontend** (Vitest + Testing Library + jsdom): `docker exec ollama_frontend npm test` — covers Zustand stores and the streaming hook.
- **CI**: `.github/workflows/ci.yml` runs both on push/PR plus ruff/black/mypy/eslint/tsc and a Docker image build. See [CLAUDE.md](./CLAUDE.md) for the dev-loop details.

## Troubleshooting

**Ollama connection failed**
- Ensure Ollama is running on the host: `ollama serve`
- Verify the model your chats are configured to use is actually installed: `ollama list`. The default chat model can be changed from the **Settings** view in the app.

**Database connection error**
- `make clean && make dev` to start with a fresh database. **This wipes all data.**
- Confirm `POSTGRES_PASSWORD` is set in `.env`.

**Port already in use**
- Most often a stale Docker container with a leaked port reservation. `docker compose down` clears project state; if it persists, `lsof -nP -iTCP:<port>` finds the holder.

**Upgrading from a pre-Alembic install**
Older installs bootstrapped the schema from `postgres/init.sql` plus `Base.metadata.create_all` at startup. The repo no longer ships that path — Alembic is the single source of truth. **Once** on an existing install:

```bash
docker exec ollama_backend alembic stamp 005bd22e40f1
docker exec ollama_backend alembic upgrade head
```

`stamp` records the existing schema as the initial revision (preventing duplicate-table errors); `upgrade head` then applies any newer migrations. Fresh installs need neither.

## License

MIT
