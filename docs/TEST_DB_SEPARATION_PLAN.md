# Test Database Separation

**Target executor:** Sonnet 4.6.
**Scope:** Move the pytest suite onto a dedicated database so tests never touch the developer's dev DB. Retire the snapshot/restore quick-fix in `test_rag.py`.

---

## Context

`backend/tests/conftest.py` runs tests in-process against the FastAPI app via `httpx.ASGITransport`. The docstring spells out the problem:

> "Tests run in-process against the FastAPI app via httpx.ASGITransport — no network, no uvicorn. **They hit the real configured database**; each test that needs persistence creates a fresh Chat row and cascade-deletes it on teardown."

Several fixtures take this further with blanket `DELETE WHERE user_id == DEFAULT_USER_ID` wipes (most notably `test_rag.py::_isolate_rag_servers`, before commit `8c104d8`). Running `make test` repeatedly destroyed the developer's persisted data — RAG server entries, project rows, etc. The current quick-fix snapshots and restores those rows in memory per test, but the underlying design is still fragile: any new fixture that does a blanket wipe will reintroduce the bug, and FK `ON DELETE RESTRICT` constraints (e.g. `courses.rag_server_id`) prevent the snapshot wipe from even running once the user accumulates linked rows.

The clean fix is to give pytest its own database (`ollama_chat_test`) so tests can wipe freely without consequence.

### Out of scope

- Switching to in-memory SQLite. The codebase relies on Postgres-specific features (`JSONB`, `UUID`, enum types, `ON CONFLICT`). SQLite would mask compatibility issues.
- Per-test transaction rollback. Cleaner pattern but a bigger rewrite (every fixture has to participate); we'd need a `nested savepoint` pattern that doesn't play well with the current `AsyncSessionLocal` design where the app and the test fixture open independent sessions. Skip for v1.
- Spinning up a separate Postgres container for tests. The same container can host both `ollama_chat` and `ollama_chat_test` databases — less infra, same isolation guarantees.

---

## Locked decisions

| Axis | Choice |
| --- | --- |
| Test DB location | Same Postgres container, separate DB named `ollama_chat_test` |
| Database URL handling | `DATABASE_URL_TEST` env var; conftest sets `DATABASE_URL=<test>` BEFORE `app.main` is imported |
| Schema setup | Session-scoped pytest fixture runs `alembic upgrade head` against the test DB once per session |
| Test data hygiene | Tests can use blanket `DELETE WHERE user_id == DEFAULT_USER_ID` again; no snapshot/restore needed |
| Quick-fix retirement | `_isolate_rag_servers` reverts to a simpler `_wipe_rag_servers` once the test DB is in place |
| CI compatibility | CI already runs `alembic upgrade head` in a fresh DB, so it only needs the env-var change |

---

## Files to change

| Phase | Path | Change |
| --- | --- | --- |
| 1 | `.env` / `.env.example` | Add `POSTGRES_TEST_DB=ollama_chat_test` and `DATABASE_URL_TEST=...` |
| 1 | `docker-compose.yml` | Add an init script (or `POSTGRES_MULTIPLE_DATABASES` pattern) so the test DB is created alongside the main DB |
| 2 | `backend/tests/conftest.py` | At module top, set `os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]` BEFORE the `from app.main import app` line |
| 2 | `backend/tests/conftest.py` | Add a session-scoped autouse fixture that runs `alembic upgrade head` against the test DB |
| 3 | `backend/tests/test_api/test_rag.py` | Revert `_isolate_rag_servers` back to a simple `_wipe_rag_servers` (blanket delete is safe again) |
| 4 | `.github/workflows/ci.yml` | Set `DATABASE_URL_TEST` env var for the pytest job; ensure the postgres service container creates both DBs |
| 5 | `Makefile` | Document `make test` behavior; optionally add `make test-reset-db` to drop+recreate the test DB |

---

## Phase 1 — Provision the test database

### 1.1 Add env vars

Update `.env.example` (and `.env` for the developer):

```env
# Test database — pytest runs against this, never the main one.
POSTGRES_TEST_DB=ollama_chat_test
DATABASE_URL_TEST=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_TEST_DB}
```

### 1.2 Auto-create the test database on container init

Postgres' official image runs any `*.sh` / `*.sql` in `/docker-entrypoint-initdb.d` on first init. Add a script:

```bash
# postgres/init/01-create-test-db.sh
#!/usr/bin/env bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
    CREATE DATABASE ${POSTGRES_TEST_DB:-ollama_chat_test};
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_TEST_DB:-ollama_chat_test} TO ${POSTGRES_USER};
EOSQL
```

Mount it via `docker-compose.yml` under the postgres service:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
  - ./postgres/init:/docker-entrypoint-initdb.d:ro
```

**Caveat:** init scripts run only on FIRST initialization of an empty volume. For existing developers, document a manual `CREATE DATABASE ollama_chat_test;` step OR add a `make test-init-db` target that runs the SQL idempotently.

### 1.3 Phase 1 verification

```
make down && make up
docker exec ollama_postgres psql -U ollama_admin -d ollama_chat -c "\l" | grep ollama_chat_test
```

Should list `ollama_chat_test` as a database.

### 1.4 Phase 1 commit

```
git add .env.example docker-compose.yml postgres/init/01-create-test-db.sh
git commit -m "feat(tests): provision ollama_chat_test database for pytest"
```

---

## Phase 2 — Point pytest at the test DB

### 2.1 Set DATABASE_URL before app imports

In `backend/tests/conftest.py`, the very first thing (before any `from app.…` import):

```python
import os

# Tests MUST run against the dedicated test DB. Set this before importing
# anything from `app`, because `app.db.session` builds the engine at import
# time using the current DATABASE_URL.
_test_url = os.environ.get("DATABASE_URL_TEST")
if not _test_url:
    raise RuntimeError(
        "DATABASE_URL_TEST is not set. Add it to .env (see .env.example) "
        "or export it before running pytest."
    )
os.environ["DATABASE_URL"] = _test_url
```

### 2.2 Run migrations once per session

Add a session-scoped autouse fixture (right after the `event_loop` fixture):

```python
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    """Run `alembic upgrade head` against the test DB once per session."""
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = AlembicConfig(str(alembic_ini))
    # The alembic env reads DATABASE_URL, which we set above.
    command.upgrade(cfg, "head")
    yield
    # No teardown — the test DB persists between runs (faster than dropping).
```

### 2.3 Confirm app's seed lifespan still runs

`app.main.lifespan` seeds the default user + Settings row. ASGI app startup happens lazily inside `httpx.ASGITransport`. The first request through `async_client` will trigger lifespan, which seeds the test DB exactly the way it seeds the dev DB.

### 2.4 Phase 2 verification

```
docker exec ollama_backend pytest tests/test_api/test_rag.py -v
docker exec ollama_postgres psql -U ollama_admin -d ollama_chat -c "SELECT COUNT(*) FROM rag_servers WHERE user_id = '00000000-0000-0000-0000-000000000001';"
```

The pytest run should pass. The dev DB count should match its pre-test value (no longer wiped).

### 2.5 Phase 2 commit

```
git add backend/tests/conftest.py
git commit -m "feat(tests): point pytest at ollama_chat_test database"
```

---

## Phase 3 — Retire the snapshot/restore quick-fix

`backend/tests/test_api/test_rag.py::_isolate_rag_servers` becomes a normal blanket-wipe fixture again, because there's no dev data in the test DB to protect.

### 3.1 Revert the fixture

```python
@pytest.fixture(autouse=True)
async def _wipe_rag_servers():
    """Each test starts with a clean slate of RAG servers for the default user."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(RagServer).where(RagServer.user_id == DEFAULT_USER_ID)
        )
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(RagServer).where(RagServer.user_id == DEFAULT_USER_ID)
        )
        await session.commit()
```

### 3.2 Phase 3 verification

`make test` — full suite green. Spot-check by planting a row in the dev DB before tests and confirming it survives:

```
docker exec ollama_postgres psql -U ollama_admin -d ollama_chat -c "INSERT INTO rag_servers (id, user_id, name, url, corpus_id) VALUES (gen_random_uuid(), '00000000-0000-0000-0000-000000000001', 'guard-row', 'http://guard:1', 'g');"
docker exec ollama_backend pytest tests/test_api/test_rag.py -v
docker exec ollama_postgres psql -U ollama_admin -d ollama_chat -c "SELECT name FROM rag_servers WHERE name = 'guard-row';"
```

### 3.3 Phase 3 commit

```
git add backend/tests/test_api/test_rag.py
git commit -m "fix(tests): retire snapshot/restore now that test DB is separate"
```

---

## Phase 4 — CI

`.github/workflows/ci.yml` already runs `alembic upgrade head` in CI. Two changes:

1. The job's postgres service container needs the same `01-create-test-db.sh` init script mounted. Either commit it into the repo and reference it in the workflow's `services.postgres.volumes`, or do `psql -c "CREATE DATABASE ollama_chat_test;"` as a workflow step before pytest.
2. Set `DATABASE_URL_TEST` in the pytest step's env block.

### 4.1 Phase 4 verification

Push a branch, watch CI go green.

### 4.2 Phase 4 commit

```
git add .github/workflows/ci.yml
git commit -m "ci(tests): run pytest against ollama_chat_test database"
```

---

## Phase 5 — Developer ergonomics

Document the new flow in `CLAUDE.md` (or wherever the test instructions live) and add a Makefile target for the rare case where the test DB needs a hard reset:

```makefile
test-reset-db: ## Drop and recreate the test database
	docker exec ollama_postgres psql -U $(POSTGRES_USER) -d postgres -c "DROP DATABASE IF EXISTS ollama_chat_test;"
	docker exec ollama_postgres psql -U $(POSTGRES_USER) -d postgres -c "CREATE DATABASE ollama_chat_test;"
	docker exec ollama_backend alembic upgrade head
```

(Reads `POSTGRES_USER` from the makefile env, same pattern as `backup`.)

### 5.1 Phase 5 commit

```
git add Makefile CLAUDE.md
git commit -m "docs(tests): document test-DB workflow and add test-reset-db target"
```

---

## End-to-end verification

After all five phases:

1. `make down && make up` — services come up, both `ollama_chat` and `ollama_chat_test` exist.
2. Plant a sentinel row in the dev DB: `INSERT INTO rag_servers (... 'sentinel' ...)`.
3. `make test` — full suite green.
4. Verify sentinel row still present in dev DB; verify nothing in `ollama_chat_test.rag_servers` (test wiped it).
5. CI green on a fresh PR.

---

## Risk callouts for the executor

- **`app.db.session` builds the engine at import time.** Setting `DATABASE_URL` after `from app.db.session import AsyncSessionLocal` is too late. Conftest must export the env var before any `app.…` import. Use a top-of-file `os.environ[...] = ...` block, not a pytest fixture.
- **The init script runs on first volume init only.** Existing developers will need to manually create the DB (or run `make test-reset-db`). Document this in Phase 5.
- **CI's postgres service** may differ in how it loads init scripts (depending on the action version). Verify by reading the workflow before assuming.
- **Don't drop and recreate the test DB on every session** — slow, breaks the migrations cache. `alembic upgrade head` is idempotent and fast against an already-migrated DB. Use `test-reset-db` only when you need a hard reset.
- **The conftest event_loop fixture is session-scoped**; the migration fixture must depend on the same scope or be session-scoped itself, otherwise migrations run inside an already-bound event loop.

---

## Critical files (read-first reference list)

- `backend/tests/conftest.py` — session-scoped event_loop, async_client, test_chat fixtures. Top of file is where DATABASE_URL must be set.
- `backend/tests/test_api/test_rag.py` — currently has the snapshot/restore quick-fix; Phase 3 reverts it.
- `backend/app/db/session.py` — engine + AsyncSessionLocal singleton. Reads DATABASE_URL at import.
- `backend/app/main.py::lifespan` — runs `alembic upgrade head` + seeds default user/settings. Tests reuse this implicitly through the first ASGI request.
- `backend/alembic.ini` + `backend/alembic/env.py` — alembic config; reads DATABASE_URL.
- `docker-compose.yml` — postgres service; volume mounts.
- `.github/workflows/ci.yml` — CI postgres service container + pytest job.
