# Self-hosted internet search tool (`search_internet`) backed by SearXNG

## Context

Agent mode today gives the model a single `search_wikipedia` tool wired to the project's local-Wikipedia RAG server. That makes agent mode useful for factual recall against a curated corpus, but it can't answer questions about anything outside that corpus (news, current events, niche topics, anything the user hasn't ingested).

We want to extend agent mode with a self-hosted internet search capability — no third-party API keys, no per-query cost, no external telemetry — to match the spirit of the rest of this self-hosted stack. The chosen approach is **SearXNG**, an open-source metasearch engine that aggregates results from public search engines (Google/Bing/DuckDuckGo/Brave/etc.) and exposes a JSON API. SearXNG slots into the existing docker-compose architecture identically to how the RAG server already does.

**Design decisions (resolved with user):**
- **Config home**: env-var only (`SEARXNG_BASE_URL`). SearXNG is bundled into the install via docker-compose; there's no per-user variance to model.
- **Agent precondition**: loosened — agent mode requires *at least one tool* (RAG configured OR web search enabled). Today it strictly requires full RAG config.
- **Citations**: inline Markdown URLs in the streamed prose for v1. No schema change, no new migration, no new frontend component. The model is instructed via system prompt to cite via `[Title](URL)`.

## Architecture

```
┌─────────┐    NDJSON     ┌──────────┐   POST /search   ┌──────────┐
│ browser ├──────────────►│ backend  ├─────────────────►│ searxng  │
└─────────┘  /agent       │ (FastAPI)│   ?format=json   │ (Docker) │
                          └──────────┘                  └────┬─────┘
                                                             │ scrapes
                                                             ▼
                                                  Google/Bing/DDG/...
```

Agent loop in `agent_service.py` (already streams one tool-use call per iteration) gains a second tool entry. Project model gains a `web_search_enabled` boolean parallel to `rag_enabled`. Tool list passed to Ollama is built from whichever tools the project has configured.

## Critical files

### Backend — new
- `backend/app/services/searxng_service.py` — async httpx client, mirrors `rag_service.py` structure (lazy `AsyncClient`, `_normalize_base_url`, dedicated exceptions). One method: `async def search(query: str, top_k: int) -> List[Dict]` returning `[{title, url, content, engine}, ...]`.
- `backend/alembic/versions/<ts>_add_project_web_search_enabled.py` — single-column migration adding `projects.web_search_enabled` boolean (default false, not null, server_default `'false'`).
- `searxng/settings.yml` — SearXNG config file mounted into the container, with `search.formats: [html, json]` (JSON output is opt-in upstream) and a sane engine selection. Committed to the repo.

### Backend — modified
- `backend/app/core/config.py` — add `searxng_base_url: str = Field(default="http://searxng:8080", ...)`.
- `backend/app/db/models/project.py` — add `web_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)`.
- `backend/app/schemas/project.py` — add `web_search_enabled: bool = False` to `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`.
- `backend/app/utils/exceptions.py` — add `SearxngConnectionError`, `SearxngValidationError` (mirroring `RagConnectionError` etc.).
- `backend/app/services/agent_service.py` — **the bulk of the change**:
  - Add `SEARCH_INTERNET_TOOL` schema (one `query: string` param).
  - Add `_execute_search_internet(args, project) -> Tuple[str, List, bool]` returning `(tool_text_for_model, [], False)`. Web hits don't aggregate into `rag_citations`, so the second/third tuple slots stay empty/false — we leak nothing into the existing citations field.
  - Format tool text as numbered list: `[1] Title\nURL\nsnippet\n\n[2] ...`.
  - Register `"search_internet"` in the `TOOLS` dict.
  - Add `_prevalidate_tool_call` branch for empty queries.
  - **Build the `tools=[...]` list dynamically** based on project config: include `SEARCH_WIKIPEDIA_TOOL` iff project has full RAG config, include `SEARCH_INTERNET_TOOL` iff `project.web_search_enabled`.
  - Update `AGENT_SYSTEM_PROMPT` to:
    - Describe both tools and when each is appropriate (Wikipedia for stable facts, internet for current events / non-Wikipedia topics).
    - Instruct the model to cite web results inline as `[Title](URL)`.
    - Conditional: the prompt should be assembled based on which tools are actually active, so the model isn't told about a tool it can't call. Add a small `_build_system_prompt(has_rag, has_web)` helper.
- `backend/app/api/v1/endpoints/messages.py`:
  - Replace `_project_has_full_rag_config(project)` gate in `stream_agent_response` (line 774) with a new `_project_has_any_agent_tool(project)` that returns true if RAG is fully configured OR `project.web_search_enabled`. Update the 400 error message to reflect "RAG or web search".
  - Keep `skip_rag=True` in `_prepare_stream` — auto-RAG pre-injection still only matters when the model isn't driving tool calls.

### Backend — tests (`backend/tests/test_api/test_agent.py`)
- Add a fixture `_make_web_search_project()` that creates a project with `web_search_enabled=True` and NO RAG config.
- Add a fixture for a project with BOTH RAG and web search enabled.
- Add a `FakeSearxng` fixture in `conftest.py` that monkeypatches `searxng_service.search` to return a fixed result list.
- New tests:
  - `test_agent_web_only_project_can_run` — agent mode succeeds against a project with only web search enabled.
  - `test_agent_search_internet_tool_invoked` — model emits a `search_internet` tool_call, tool_result frame fires, snippet text reaches the assistant message.
  - `test_agent_empty_web_query_suppressed` — empty-query `search_internet` is pre-validated out, no `tool_call` frame emitted.
  - `test_agent_no_tools_configured_rejected` — project with neither RAG nor web search returns 400 on `/agent`.
  - Extend `test_agent_dual_tools` — project with both RAG + web search exposes both tools to the model.

### Frontend — modified
- `frontend/src/types/project.ts` — add `web_search_enabled: boolean` to the `Project` type.
- `frontend/src/stores/projectsStore.ts` — include the field in create/update payloads (the store proxies arbitrary fields, so likely just needs a type bump).
- `frontend/src/components/projects/ProjectDetail.tsx` (or wherever `rag_enabled` toggle lives) — add a parallel checkbox/toggle row "Enable web search (SearXNG)". Save handler already PATCHes the whole project, no separate endpoint needed.
- Agent-mode chat precondition: find where the UI gates the agent toggle on `rag_enabled` and loosen to `rag_enabled || web_search_enabled`. Likely in the chat settings dropdown or the agent-mode switch on `ChatContainer`.
- (No new component needed — Message body already renders Markdown links from streamed prose.)

### Frontend — tests
- Extend the ProjectDetail Vitest spec (if one exists) to cover the new toggle's persistence + the loosened agent precondition.

### Docker

`docker-compose.yml` — add a new service:

```yaml
  searxng:
    image: searxng/searxng:latest
    container_name: ollama_searxng
    restart: unless-stopped
    environment:
      SEARXNG_BASE_URL: http://searxng:8080/
      SEARXNG_SECRET: ${SEARXNG_SECRET:-change-me-in-env}
    volumes:
      - ./searxng:/etc/searxng:rw
    networks:
      - ollama_network
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
```

Add `searxng` to the backend service's `depends_on`. No dev override needed — SearXNG behaves the same in dev and prod.

`.env.example` — add `SEARXNG_SECRET=change-me` and `SEARXNG_BASE_URL=http://searxng:8080`.

### Patterns reused (do not reinvent)

- `RagService` class shape (`rag_service.py`) → mirrored verbatim for `SearxngService`.
- `_execute_search_wikipedia` return tuple (`agent_service.py:129-174`) → web-search executor returns the same tuple shape so the existing dispatch loop at lines 436-533 needs **zero changes**.
- `_prevalidate_tool_call` empty-query guard (`agent_service.py:183-197`) → extended with a `search_internet` branch.
- `_persist_assistant_message` (`messages.py:562-592`) → already handles arbitrary `tool_calls` audit; no change needed.
- `ToolCalls.tsx` rendering → already renders any `{id, name, input, ok, summary, error}` shape; works for `search_internet` unchanged.

## Verification

Run end-to-end against a real SearXNG instance:

1. `make clean && make dev` — start the stack. Wait for the `searxng` container to report healthy (`docker ps`).
2. `curl 'http://localhost:8888/search?q=mistral+ai&format=json' | jq '.results[0]'` — confirm SearXNG returns JSON results. If you see HTML or a 403, the `settings.yml` JSON-format toggle isn't applied — fix the mount.
3. In the UI: create a new project, toggle **Enable web search** on, leave RAG off, save.
4. Create a chat in that project, toggle agent mode on (should now be enabled despite RAG being off — this verifies the loosened precondition).
5. Send a question that requires fresh web knowledge (e.g. "What was announced at re:Invent 2025?"). Confirm in the streamed output:
   - A `tool_call` frame fires with `name: "search_internet"`.
   - A `tool_result` frame follows with `ok: true`.
   - The assistant's final text contains inline Markdown links to web pages.
6. Send small talk ("hey") — confirm no tool call is made (pre-validation + system prompt should suppress).
7. Repeat in a project with BOTH RAG and web search enabled. Ask a question requiring both ("Compare what Wikipedia says about LLaMA with the latest 2025 reporting"). Confirm both tools fire in sequence.
8. Run the suite: `make test` (backend) and `docker exec ollama_frontend npm test` (frontend). All new tests in `test_agent.py` pass.
9. `make lint && make format` — clean.
10. Sanity-check the migration: `make migrate-down && make migrate-up` round-trips without error.

## Out of scope (deliberate)

- `fetch_url` companion tool — useful follow-up but adds substantial complexity (HTML cleaning, JS pages need a headless browser, content-length budget). Snippets-only `search_internet` covers the majority of factual queries on its own.
- Structured `web_citations` schema column / dedicated frontend component — defer until inline-URL UX is shown to be insufficient.
- SearXNG rate-limiting / proxy rotation — single-user self-hosted use will not hit limits; add `searx.cooldown` or a SOCKS proxy later if needed.
- Per-user SearXNG instance picker — deliberate: only one bundled SearXNG, env-var configured.
- Wiring SearXNG into auto-RAG (non-agent `/stream`) — agent mode is the explicit gate for tool use; the user picks agent mode when they want web access.
