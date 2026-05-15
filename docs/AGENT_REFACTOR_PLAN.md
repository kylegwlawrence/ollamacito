# Agent Service Refactor: Streaming Tool Calls via Modern Ollama Client

## Context

`backend/app/services/agent_service.py` currently uses raw `httpx` calls to `/api/chat` and a two-call-per-iteration pattern (non-streaming detection with `tools=`, then a separate streaming call for the final prose answer). This was necessary because:

1. The pinned `ollama==0.1.6` Python client predates the `tools=` parameter (`agent_service.py:14`).
2. Older Ollama servers (<0.5.x) only returned `tool_calls` on non-streaming responses.

The user has now upgraded the local Ollama server to **0.24.x**, which supports streaming + tool calls together. The goal: bump the `ollama` Python client, drop the `httpx` shim, and collapse to **one streaming call per iteration**. Wins:

- **Typewriter UX during tool-deciding turns.** Today, reasoning text returned alongside a `tool_call` arrives as a single atomic chunk (because the detection pass is non-streaming, `agent_service.py:385-387`). After the rewrite, that reasoning streams character-by-character — closer to how mainstream tool-using chat UIs render.
- **Code simplification.** The `httpx` shim and the "Option B" preamble disappear; tool dispatch logic stays.
- **Single conceptual model.** No more "detect pass, then maybe a fallback stream pass" — every iteration is just one streaming call (with one targeted exception for the empty-turn safety net, see Phase B).

Non-claim worth being honest about: this does NOT reduce HTTP round-trips in the common case. When today's detection returns content with no `tool_calls`, that content IS the final answer and no second call fires (`agent_service.py:389-392`). The only round-trip "saved" is in the rarely-hit empty-content fallback path.

Per discussion, this is a **two-phase rollout** for safer rollback:

- **Phase A** bumps the `ollama` Python client and confirms the non-agent paths (regular `/stream`, title generation, memory generation) still behave identically.
- **Phase B** rewrites `agent_service.py` to use the new streaming-with-tools API.
- **Phase C** rewrites the agent tests to mock the new client API surface.
- **Phase D** is manual end-to-end verification.

## Out of scope

- **Frontend changes.** `frontend/src/stores/streamingStore.ts` already handles `chunk`, `tool_call`, and `tool_result` frames in any interleaving (verified at lines 98–131). The NDJSON frame contract is preserved.
- **Upfront tools-capability validation.** Per user decision, models that lack the `tools` capability will silently produce a non-agent answer (current behavior).
- **Back-compat with older Ollama servers.** Single-user self-hosted, host already upgraded.

## Decisions (already locked in)

| Decision | Choice |
|----------|--------|
| PR scope | Two-phase (Phase A separately mergeable from Phase B) |
| Client instance | Agent reuses `ollama_service.client` (shared `AsyncClient` singleton) |
| Tools-capability check | None — silent degradation as today |

---

## Phase A — Bump the `ollama` Python client

### Files

- `backend/requirements.txt`
- `backend/app/services/ollama_service.py` (verify, possibly tweak chunk access)

### Steps

1. **Pick a target version.** Check PyPI for the current stable `ollama` Python package (as of early 2026, likely `0.4.x` or `0.5.x`). Cross-reference its changelog/source to confirm:
   - `AsyncClient.chat(model, messages, tools=[...], stream=True)` is supported.
   - Streamed chunks expose `.message.content` (str) and `.message.tool_calls` (`list | None`) where each tool call has `.function.name` (str) and `.function.arguments` (dict).
   - `AsyncClient.list()` still returns something `.get("models", [...])`-compatible.

   Pin to a specific minor version (e.g. `ollama==0.4.7`), not a range. Update `backend/requirements.txt:15`.

2. **Migrate `ollama_service.py` from dict-style `.get()` access to attribute access.** ollama-python 0.4+ returns Pydantic models (`ChatResponse`, `ListResponse`, `Message`) built on a `SubscriptableBaseModel`. That base class typically defines `__getitem__` and `__setitem__` for backwards compat, but **does NOT implement `.get()`** — `.get()` is a `dict` method, not a Pydantic one. Every `.get()` call on a response object will likely raise `AttributeError: '<Model>' object has no attribute 'get'`.

   **Verify against the pinned version first** before assuming the migration is needed:

   ```bash
   docker exec ollama_backend python -c \
     "from ollama import ChatResponse; \
      r = ChatResponse(message={'role':'assistant','content':''}); \
      print(r.get('message'))"
   ```

   If that raises `AttributeError`, the migration is required.

   **Sites to migrate** (line numbers from current `ollama_service.py`):

   | Line | Current | Replacement |
   |---|---|---|
   | 67 | `response.get("models", [])` | `response.models` (`ListResponse.models` is a `list[Model]`) |
   | 89 | `m.get("name", "").split(":")[0]` | Use the correct field on `Model` — likely `m.model` (verify); fallback `getattr(m, "model", "") or ""` |
   | 91 | `model_name in m.get("name", "")` | `model_name in (getattr(m, "model", "") or "")` |
   | 158 | `response.get("message", {}).get("content", "")` | `(response.message.content if response.message else "")` |
   | 205–206 | `if "message" in chunk: content = chunk["message"].get("content", "")` | `content = chunk.message.content if getattr(chunk, "message", None) else ""` |
   | 320 | `response.get("message", {}).get("content", "").strip()` | `(response.message.content if response.message else "").strip()` |
   | 399 | `response.get("message", {}).get("content", "").strip()` | `(response.message.content if response.message else "").strip()` |

   Do not change function signatures or return shapes. Keep the same outer exception handling. If `SubscriptableBaseModel` in the pinned version DOES implement `.get()` (some forks add it), the migration becomes optional but still recommended for clarity and forward-compat.

3. **Rebuild the backend image.** `make down && make dev` (or `docker compose build backend && make dev`).

### Phase A verification

- `make test` — full pytest suite passes. **Critical**: `tests/test_api/test_messages.py`, `test_file_attachment.py`, and `test_models.py` still pass with the new client (these exercise `OllamaService.stream_chat` via `FakeOllama` in `conftest.py:107–116`).
- **Manual smoke (host)**:
  - Send a regular (non-agent) message in a chat → typewriter streaming works end-to-end.
  - Send a chat message that triggers project-level RAG → citations render.
  - Trigger project memory generation on a project with ≥1 chat → completes and saves.
  - Have a chat reach its first complete assistant turn → title generation fires (check backend logs / DB).

### Phase A acceptance

Non-agent paths behave identically with the new client. `agent_service.py` is **untouched** and continues to work via its existing `httpx` shim. Commit Phase A separately.

---

## Phase B — Rewrite `agent_service.py`

### Files

- `backend/app/services/agent_service.py` (significant rewrite)

### Imports

- **Remove**: `import httpx`
- **Add**: `from app.services.ollama_service import ollama_service`
- **Add**: `from ollama import ResponseError` (preserves today's HTTP-status granularity in the per-iteration error path)

### Delete

- `_ollama_chat_nonstream()` — currently `agent_service.py:125–149`
- `_ollama_chat_stream()` — currently `agent_service.py:152–195`
- The "Why call Ollama directly via httpx" paragraph from the module docstring (`agent_service.py:14–17`) and the "Option B" preamble (`agent_service.py:5–13`).

### Keep unchanged

- `SEARCH_WIKIPEDIA_TOOL` (`agent_service.py:53–79`)
- `AGENT_SYSTEM_PROMPT` (`agent_service.py:82–89`)
- `_TOOL_TOP_K_CAP = 3` (`agent_service.py:95`)
- `_AGENT_MIN_NUM_CTX = 8192` (`agent_service.py:101`)
- `AgentRunResult` dataclass (`agent_service.py:107–119`) — `result` is consumed by `messages.py:816–823`, **do not change its shape**.
- `_execute_search_wikipedia()` (`agent_service.py:201–246`) and the `TOOLS` registry (`agent_service.py:250–252`)
- `_agent_options()` (`agent_service.py:258–263`)
- `_build_citations()` (`agent_service.py:266–290`)

### New module docstring

```python
"""
Agent service: drives a tool-calling loop against Ollama using one streaming
call per iteration.

Loop:
  while iterations < cap:
      stream a chat call with tools=[search_wikipedia]
      accumulate emitted content chunks + any tool_calls
      if no tool_calls were emitted:
          if no content was emitted either:
              fire one tool-free streaming fallback (safety net for tool-aware
              models that emit empty turns when given tools)
          the streamed content (this turn or fallback) IS the final answer -> done
      else:
          dispatch each tool, append result to messages, continue
  on iteration cap: force one more streaming call with tools omitted

Tools available in v1: `search_wikipedia` only — a thin wrapper over RagService.
Citations from every tool invocation are aggregated and stored on the final
assistant message in the same shape as the non-agent flow.
"""
```

### Rewrite `run_agent()`

Structure stays the same — only the inside of the per-iteration body changes. Pseudocode for the new body:

```python
async def run_agent(...):
    # === unchanged pre-flight (agent_service.py:309–325) ===
    # fetch /rag/info; build article_url_template; emit error frame on failure.
    # === unchanged prelude (agent_service.py:328–345) ===
    # build messages = [system_prompt] + initial_messages
    # agent_options = _agent_options(options)
    # aggregated_hits, used_dense_any, accumulated_text, _commit_citations()

    for iter_idx in range(max_iters):
        if await is_disconnected():
            result.truncated = True
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            return

        # ONE streaming call per iteration. May yield content chunks and/or
        # tool_calls in the same stream (tool_calls typically arrive in the
        # final chunks before done=True, but we accept any ordering).
        turn_content_parts: List[str] = []
        turn_tool_calls: List[Dict[str, Any]] = []
        disconnected_mid_turn = False

        try:
            stream = await ollama_service.client.chat(
                model=model,
                messages=messages,
                tools=[SEARCH_WIKIPEDIA_TOOL],
                options=agent_options,
                stream=True,
            )
            async for chunk in stream:
                if await is_disconnected():
                    disconnected_mid_turn = True
                    result.truncated = True
                    break

                msg = getattr(chunk, "message", None)
                if msg is None:
                    continue

                content = getattr(msg, "content", "") or ""
                if content:
                    yield {"type": "chunk", "content": content}
                    accumulated_text.append(content)
                    turn_content_parts.append(content)

                raw_calls = getattr(msg, "tool_calls", None) or []
                for tc in raw_calls:
                    fn = getattr(tc, "function", None)
                    if fn is None:
                        continue
                    name = getattr(fn, "name", "") or ""
                    raw_args = getattr(fn, "arguments", None)
                    # Defensive: ollama-python returns dict, but historically
                    # other clients have returned a JSON string. Accept both.
                    if isinstance(raw_args, str):
                        try:
                            parsed = json.loads(raw_args)
                        except json.JSONDecodeError:
                            parsed = {}
                    elif raw_args is None:
                        parsed = {}
                    else:
                        parsed = dict(raw_args)
                    turn_tool_calls.append(
                        {"function": {"name": name, "arguments": parsed}}
                    )
        except ResponseError as e:
            # Preserve today's HTTP-status granularity (agent_service.py:363-370).
            status = getattr(e, "status_code", "?")
            body = str(getattr(e, "error", e))[:200]
            err = f"Ollama returned {status}: {body}"
            logger.error("Agent loop iteration %d: %s", iter_idx, err)
            result.error = err
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            yield {"type": "error", "message": err}
            return
        except Exception as e:
            err = f"Ollama call failed: {e}"
            logger.error("Agent loop iteration %d: %s", iter_idx, err)
            result.error = err
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            yield {"type": "error", "message": err}
            return

        if disconnected_mid_turn:
            # Don't dispatch any partial tool_calls and don't start another
            # iteration — the client is gone.
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            return

        if not turn_tool_calls:
            # If the model emitted NEITHER tool_calls NOR content this turn,
            # fall back to one tool-free streaming call. This preserves today's
            # safety net (agent_service.py:393-412) for the degenerate case
            # where a tool-aware model emits an empty turn but answers normally
            # without tools. Cheap (~25 lines), eliminates a known regression
            # vector for some models.
            if not turn_content_parts:
                try:
                    fallback_stream = await ollama_service.client.chat(
                        model=model,
                        messages=messages,
                        options=agent_options,  # NB: no `tools=` -> prose only
                        stream=True,
                    )
                    async for chunk in fallback_stream:
                        if await is_disconnected():
                            result.truncated = True
                            break
                        msg = getattr(chunk, "message", None)
                        content = getattr(msg, "content", "") if msg else ""
                        if content:
                            yield {"type": "chunk", "content": content}
                            accumulated_text.append(content)
                except Exception as e:
                    err = f"Empty-turn fallback failed: {e}"
                    logger.error(err)
                    result.error = err
                    result.final_content = "".join(accumulated_text)
                    _commit_citations()
                    yield {"type": "error", "message": err}
                    return

            # Streamed content (from this turn or the fallback) IS the final answer.
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            yield {"type": "done", "truncated": result.truncated}
            return

        # Record the assistant tool-calling turn for the next iteration's context.
        messages.append({
            "role": "assistant",
            "content": "".join(turn_content_parts),
            "tool_calls": turn_tool_calls,
        })

        # === UNCHANGED tool dispatch loop (agent_service.py:428–511) ===
        # for tc in turn_tool_calls:
        #     emit tool_call frame, look up handler, run, emit tool_result frame,
        #     append audit entry, append {"role":"tool","content": ...} to messages

    # Iteration cap exit — force ONE streaming call with tools omitted.
    logger.info("Agent loop hit iteration cap (%d); forcing final answer", max_iters)
    result.truncated = True
    try:
        stream = await ollama_service.client.chat(
            model=model,
            messages=messages,
            options=agent_options,  # NB: no `tools=` -> model emits prose only
            stream=True,
        )
        async for chunk in stream:
            if await is_disconnected():
                break
            msg = getattr(chunk, "message", None)
            content = getattr(msg, "content", "") if msg else ""
            if content:
                yield {"type": "chunk", "content": content}
                accumulated_text.append(content)
    except Exception as e:
        err = f"Forced-final-answer generation failed: {e}"
        logger.error(err)
        result.error = err
        result.final_content = "".join(accumulated_text)
        _commit_citations()
        yield {"type": "error", "message": err}
        return

    result.final_content = "".join(accumulated_text)
    _commit_citations()
    yield {"type": "done", "truncated": True}
```

### Edge cases the rewrite handles

1. **Empty turn (no content, no tool_calls)**: Falls into the `if not turn_tool_calls` branch. Because `turn_content_parts` is also empty, the **tool-free fallback streaming call** fires (preserving `agent_service.py:393-412`'s safety net). Then yields `done`. If the fallback also produces nothing, the endpoint's persistence guard (`messages.py:816` — `if result.final_content or result.tool_calls_audit`) prevents an empty message row.

2. **Disconnect mid-stream**: Detected between chunks; sets `disconnected_mid_turn=True` and `result.truncated=True`, then exits cleanly without dispatching partial tool_calls or starting another iteration. Partial `accumulated_text` is preserved into `result.final_content` so the persistence layer captures it as a truncated message.

3. **`tc.function.arguments` shape**: defensively handles `dict` / `Mapping` (current ollama-python `arguments: Mapping[str, Any]`), `str` (JSON-encoded — historical / future fallback), and `None`.

4. **Multiple chunks emitting `tool_calls`**: accumulated into `turn_tool_calls` across the whole stream, dispatched in order after the stream completes.

5. **Mixed-turn (content + tool_calls in same stream)**: content streams to the client as it arrives, tool_calls dispatch after the stream finishes. Order in the NDJSON output: `chunk` ... `chunk` ... `tool_call` ... `tool_result` ... `chunk` (next iteration).

6. **Disconnect-frame consistency (intentional behavioral cleanup)**: Today's code is inconsistent — top-of-loop disconnect (`agent_service.py:347-353`) yields nothing before returning, but mid-prose-stream disconnect (`agent_service.py:413-415`) yields a `done` frame with `truncated=True` first. The rewrite unifies this: disconnects never yield a `done` frame. Functionally identical from the client's POV (the socket is dead anyway), but cleaner. Server-side persistence still captures the truncated message.

7. **HTTP errors from Ollama**: caught by the dedicated `except ResponseError` arm to preserve today's `httpx.HTTPStatusError` granularity (`agent_service.py:363-370`). Generic `except Exception` remains as the fallback for non-HTTP failures (timeouts, JSON decode, network errors before the response).

### Phase B verification

`make test` should still pass once Phase C is also done. Standalone Phase B verification: skip — Phase B alone would break the mocked tests since they patch `_ollama_chat_nonstream` / `_ollama_chat_stream`, which no longer exist. Phase B and Phase C must merge together.

---

## Phase C — Update tests

### Files

- `backend/tests/test_api/test_agent.py`

### Mock target shift

The old mocks patched two private functions in `agent_service`. The new agent calls `ollama_service.client.chat(...)`. We need to patch the bound method on the singleton client.

**Approach**: monkeypatch `app.services.ollama_service.ollama_service.client.chat` (via `agent_service.ollama_service.client` for the import path the agent uses).

### New fake

Replace `FakeAgentOllama` (`test_agent.py:145–187`) with a streaming-only fake. The agent now only calls `client.chat(stream=True)`.

```python
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List, Optional

class FakeAgentStream:
    """Scriptable replacement for ollama_service.client.chat.

    Configure:
      - turn_scripts: list of "turns". Each turn is a list of "chunks".
        Each chunk dict may have:
          {"content": str}                 -> contributes to message.content
          {"tool_calls": [{"function": {"name": str, "arguments": dict}}, ...]}
        Chunks are emitted in order.
      - error: exception raised on the next call (mimics Ollama failure).

    Inspect:
      - calls: list of kwargs each invocation received.
    """

    def __init__(self) -> None:
        self.turn_scripts: List[List[Dict[str, Any]]] = []
        self.error: Optional[Exception] = None
        self.calls: List[Dict[str, Any]] = []
        self._turn_idx = 0

    async def __call__(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self._turn_idx >= len(self.turn_scripts):
            raise AssertionError(
                f"FakeAgentStream: ran out of scripted turns (idx={self._turn_idx})"
            )
        chunks = self.turn_scripts[self._turn_idx]
        self._turn_idx += 1
        return _async_iter([_make_chat_response(c) for c in chunks])


async def _async_iter(items):
    for item in items:
        yield item


def _make_chat_response(chunk_data: Dict[str, Any]):
    """Build something that quacks like ollama.ChatResponse for getattr access."""
    raw_calls = chunk_data.get("tool_calls") or []
    tool_calls = [
        SimpleNamespace(
            function=SimpleNamespace(
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", {}),
            )
        )
        for tc in raw_calls
    ] or None
    message = SimpleNamespace(
        content=chunk_data.get("content", ""),
        tool_calls=tool_calls,
    )
    return SimpleNamespace(message=message)


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgentStream:
    fake = FakeAgentStream()
    # Patch on the module the agent imports through, so the patch is
    # effective regardless of where else ollama_service is imported.
    from app.services.ollama_service import ollama_service
    monkeypatch.setattr(ollama_service.client, "chat", fake)
    return fake
```

### Test rewrites (mechanical)

For each existing test in `test_agent.py`, port the old scripted responses into `turn_scripts`. The mapping:

| Old (two-call pattern)                                              | New (single-call-per-turn)                          |
|---------------------------------------------------------------------|-----------------------------------------------------|
| `_model_tool_call(query, content="")` (nonstream)                   | One turn with `[{"tool_calls": [...]}]` (+ optional content chunk before it) |
| `_model_final("text")` (nonstream)                                  | One turn with `[{"content": "text"}]` (no tool_calls — model is done) |
| `fake_agent.stream_chunks = [...]` (separate forced-final stream)   | The **last** turn in `turn_scripts` carries those chunks |

The `_model_tool_call` and `_model_final` helpers can be deleted; their use sites convert to `turn_scripts` entries directly.

#### Per-test changes

**`test_happy_path_tool_call_then_answer` (`test_agent.py:226–280`)**:
```python
fake_agent.turn_scripts = [
    # Turn 1: tool_call only
    [{"tool_calls": [{"function": {"name": "search_wikipedia",
                                    "arguments": {"query": "photosynthesis"}}}]}],
    # Turn 2: final answer (no tool_calls)
    [{"content": "Photosynthesis is the process by which …"}],
]
# Existing assertions unchanged. Add: assert len(fake_agent.calls) == 2
# The last call should have tools= present (single-call-per-iter, tools always
# passed except on iteration cap forced-final).
```

**`test_iteration_cap_forces_final_answer_and_marks_truncated` (`test_agent.py:284–326`)**:
```python
fake_agent.turn_scripts = (
    # 5 iterations of tool-call-only turns
    [[{"tool_calls": [{"function": {"name": "search_wikipedia",
                                     "arguments": {"query": f"q{i}"}}}]}]
     for i in range(5)]
    # 6th call is the forced-final (tools omitted)
    + [[{"content": "sorry, "}, {"content": "I had to give up"}]]
)
# Assertions:
assert len(fake_agent.calls) == 6
# Iteration-cap forced final omits tools= entirely
assert "tools" not in fake_agent.calls[-1]
```

**`test_malformed_tool_args_surface_error_and_feed_back_to_model` (`test_agent.py:330–388`)**:
```python
fake_agent.turn_scripts = [
    # Turn 1: bad tool_call (null query)
    [{"tool_calls": [{"function": {"name": "search_wikipedia",
                                    "arguments": {"query": None}}}]}],
    # Turn 2: good tool_call (recovery)
    [{"tool_calls": [{"function": {"name": "search_wikipedia",
                                    "arguments": {"query": "recovery"}}}]}],
    # Turn 3: final answer
    [{"content": "I figured it out: ok now."}],
]
# The "tool error fed back to model" assertion uses fake_agent.calls[1]
# (the second iteration's stream call) instead of nonstream_calls[1].
second_call_messages = fake_agent.calls[1]["messages"]
```

**`test_rag_get_info_failure_emits_error_frame_and_skips_loop` (`test_agent.py:392–425`)**:
```python
# fake_agent has no turn_scripts — RAG pre-flight should fail before Ollama is called.
# Assertion changes: assert len(fake_agent.calls) == 0
```

**`test_400_when_project_lacks_rag_config` (`test_agent.py:428–447`)** and **`test_404_when_chat_does_not_exist` (`test_agent.py:450–462`)**:
- Same flow — assertion changes from `fake_agent.nonstream_calls` to `fake_agent.calls`.

**`test_user_message_persists_when_ollama_fails_mid_loop` (`test_agent.py:465–495`)**:
```python
fake_agent.error = RuntimeError("ollama exploded")
# (Same shape as today; `error` is raised on first call.)
```

### New tests to add

```python
@pytest.mark.asyncio
async def test_empty_turn_triggers_tool_free_fallback(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Model emits empty content + no tool_calls in iteration 1. The agent
    should fire a tool-free fallback streaming call (preserving today's
    safety net at agent_service.py:393-412) and use its output as the answer."""
    fake_agent.turn_scripts = [
        [],  # Iteration 1: completely empty stream (no content, no tool_calls)
        [{"content": "Sure — here's a direct answer."}],  # Fallback (no tools=)
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "hi")
        assert status == 200

        # Two calls: the empty iteration + the tool-free fallback
        assert len(fake_agent.calls) == 2
        # First call has tools= (per-iteration default)
        assert fake_agent.calls[0].get("tools") is not None
        # Fallback call has tools= omitted
        assert "tools" not in fake_agent.calls[1]

        # Final answer made it to NDJSON + persisted
        types = [f["type"] for f in frames]
        assert "chunk" in types
        assert types[-1] == "done"
        assert frames[-1]["truncated"] is False

        async with AsyncSessionLocal() as session:
            assistant = (
                (await session.execute(
                    select(Message).where(
                        Message.chat_id == chat_id, Message.role == "assistant"
                    )
                )).scalars().one()
            )
        assert "direct answer" in assistant.content
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_streams_content_then_tool_call_in_same_turn(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Single streaming turn can emit reasoning chunks AND a tool_call.
    Verifies frame ordering: chunks first, then tool_call/tool_result, then
    next-turn chunks."""
    fake_rag.hits = [_hit("X", None, "x text")]
    fake_agent.turn_scripts = [
        [
            {"content": "Let me look "},
            {"content": "this up."},
            {"tool_calls": [{"function": {"name": "search_wikipedia",
                                           "arguments": {"query": "x"}}}]},
        ],
        [{"content": "The answer is x."}],
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "what is x?")
        assert status == 200

        types = [f["type"] for f in frames]
        first_tool_call_idx = types.index("tool_call")
        # At least the two "Let me look this up." chunks come before the tool_call
        assert types[:first_tool_call_idx].count("chunk") >= 2
        # And the final-answer chunk arrives after the tool_result
        first_tool_result_idx = types.index("tool_result")
        assert any(
            t == "chunk" for t in types[first_tool_result_idx + 1:]
        )

        async with AsyncSessionLocal() as session:
            assistant = (
                (await session.execute(
                    select(Message).where(
                        Message.chat_id == chat_id, Message.role == "assistant"
                    )
                )).scalars().one()
            )
        assert "Let me look this up." in assistant.content
        assert "The answer is x." in assistant.content
        assert len(assistant.tool_calls) == 1
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")
```

### Update test file docstring

`test_agent.py:1–21` describes the old monkeypatch target. Update to reference `ollama_service.client.chat`.

---

## Phase D — Manual verification (end-to-end)

After Phase B + C are merged:

1. **Backend boots cleanly.** `make dev`, check logs for import errors.
2. **Agent typewriter UX**: Open a project with full RAG config, enable agent mode on a chat, ask a factual question (e.g. "what is photosynthesis?"). Verify:
   - Reasoning text (if the model emits any) streams character-by-character (NEW behavior; previously appeared as one large chunk).
   - Tool call frame appears after the reasoning text.
   - Tool result frame lands.
   - Final answer streams character-by-character.
   - Persisted assistant message contains content + `tool_calls` audit + `rag_citations`.
3. **Conversational question** (e.g. "thanks!"): model answers directly with no `tool_call` frames. Verify done frame arrives, message persists.
4. **Mid-stream cancel**: ask a long question, cancel via the UI cancel button. Verify partial assistant message persists with `truncated=True`.
5. **RAG server down**: stop the local RAG server. Open the agent chat. Send a message. Verify a clean error frame surfaces; user message is still preserved.
6. **Iteration cap**: harder to trigger naturally — optionally lower `max_iters` to 2 temporarily and force a loop. Skip if not easily reproducible; the test covers it.
7. **`make test`** — all backend tests pass.
8. **`make lint`** — clean.
9. **Frontend Vitest**: `docker exec ollama_frontend npm test` — frontend tests pass (no frontend code changed, but confirm).

---

## Risks / watch-items

1. **Ollama-python `ChatResponse.message.tool_calls` shape may vary across client versions.** Some versions emit tool_calls only on the chunk where `done=True`; others may emit incremental chunks with `tool_calls` populated. The accumulator pattern in the rewrite handles both. If a particular model the user runs emits `tool_calls` in an unusual shape (e.g. partial JSON strings rather than dicts), the defensive `isinstance(raw_args, str)` branch covers it.

2. **`stream_chat` chunk access** in `ollama_service.py:205` — the `if "message" in chunk` test should be migrated to attribute access for clarity. Verify with Phase A smoke test.

3. **Shared `AsyncClient` connection pool**: `ollama_service.client` is now used by **both** the non-agent and agent paths. httpx pools are concurrency-safe, so this should be fine, but if the user runs concurrent agent + regular streams (unusual for a single-user app), throughput may share a single pool. Acceptable for this app's scale.

4. **No upfront tools-capability check**: a model without `tools` capability silently ignores the schema → user sees a non-agentic answer despite agent mode being on. Document in agent-mode tooltip if the user wants to mitigate (out of scope for this refactor per decision).

5. **Empty-turn fallback preserved (deliberate)**: today's tool-free fallback (`agent_service.py:393-412`) is **kept** in the rewrite as a guarded branch (see Phase B pseudocode, the `if not turn_content_parts:` block). It guards against tool-aware models that emit empty turns when given tools but answer normally when tools are absent. Cheap (~25 lines), zero behavioral regression risk vs today.

6. **No first-token latency regression expected.** Today's detection pass *also* carries the tools schema (`agent_service.py:359-362`), so the rewrite doesn't add tools to any common-path call that didn't already have them. The only tool-free calls in both old and new are the empty-turn fallback and the iteration-cap forced final. **No watch-item here**; ignore any "tools schema makes things slower" intuition.

7. **Agent's `ResponseError` exception assumes a specific ollama-python error class.** Some client versions raise `httpx.HTTPStatusError` directly without wrapping. If the version pinned in Phase A doesn't expose `ResponseError`, fall back to `except httpx.HTTPStatusError` in the agent loop. Confirm by running the agent test suite immediately after the version bump.

---

## Critical files reference

| Path | Role |
|------|------|
| `backend/app/services/agent_service.py` | Primary target of rewrite |
| `backend/app/services/ollama_service.py` | Source of the shared `AsyncClient` singleton |
| `backend/app/api/v1/endpoints/messages.py:735–846` | Agent endpoint; consumes `AgentRunResult` shape — **do not change** |
| `backend/tests/test_api/test_agent.py` | Tests to rewrite |
| `backend/requirements.txt:15` | `ollama` version pin |
| `frontend/src/stores/streamingStore.ts:98–131` | Frame dispatcher — **already** handles interleaved chunks/tool_calls; no change needed |
| `backend/tests/conftest.py:107–116` | `FakeOllama.stream_chat` for non-agent tests — leave alone unless Phase A reveals an issue |

## Verification (consolidated)

- **Tests**: `make test` passes (backend) + `docker exec ollama_frontend npm test` (frontend).
- **Lint**: `make lint` clean.
- **Manual**: the 9-step Phase D checklist above.
- **Diff size sanity check**: `agent_service.py` should shrink net ~30–50 lines. Deletions: `_ollama_chat_nonstream` (~25 lines), `_ollama_chat_stream` (~45 lines), the multi-paragraph "Option B" docstring (~20 lines). Additions back: empty-turn fallback block (~25 lines), `ResponseError` handler (~10 lines), updated module docstring (~10 lines). If the file shrinks by more than ~70 lines, you likely dropped the fallback or an error path — re-check.
