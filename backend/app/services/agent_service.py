"""
Agent service: drives an autonomous tool-calling loop against Ollama.

The loop strategy ("Option B" in the design doc):

  while iterations < cap:
      call Ollama with stream=False and tools=[search_wikipedia]
      if the model returns no tool_calls:
          re-call once with stream=True, tools=None  ->  typewriter UX on final
          break
      else:
          run each tool, append result, continue

Why call Ollama directly via httpx rather than through the pinned `ollama==0.1.6`
Python client: that client predates the `tools=` parameter. Bumping the package
would touch the existing OllamaService.stream_chat path; talking to /api/chat
directly keeps the regular streaming flow untouched.

Tools available in v1: `search_wikipedia` only — a thin wrapper over the existing
RagService. The model picks its own query and may invoke the tool repeatedly to
refine. Citations are aggregated across all invocations so the assistant message
still ends up with one consolidated rag_citations payload (same shape as the
non-agent flow).
"""

import json
import uuid as uuid_lib
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Project
from app.services.rag_service import rag_service
from app.services.rag_utils import dedupe_hits_by_page, format_rag_context

logger = get_logger(__name__)


# ----- Tool schema and prompt -------------------------------------------------

SEARCH_WIKIPEDIA_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_wikipedia",
        "description": (
            "Search the local Wikipedia knowledge base for factual information. "
            "Use this when the user asks about people, places, events, science, "
            "history, or any topic that may benefit from external reference. "
            "You may call this tool multiple times with refined queries — start "
            "broad, then narrow if results aren't relevant. Skip the tool for "
            "small talk, opinions, or questions about the conversation itself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Short search query focused on key entities and concepts. "
                        "Plain words, not a question."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


AGENT_SYSTEM_PROMPT = (
    "You are an assistant with access to a `search_wikipedia` tool that queries "
    "a local Wikipedia knowledge base. Use the tool for factual questions, but "
    "answer directly without searching for conversational, opinion-based, or "
    "self-referential questions. When you do search, cite sources inline by "
    "their bracketed title (e.g. `[French Revolution § Causes]`). You may make "
    "at most a few search calls per turn — be efficient."
)


# Cap top_k inside the agent loop so 5 iterations × top_k retrieved chunks
# can't blow num_ctx. The project's configured rag_top_k is still respected
# as an upper bound (in case the project has it set lower).
_TOOL_TOP_K_CAP = 3


# Bump num_ctx in agent mode to give the model headroom for tool results
# accumulated across iterations. Take whichever is larger so callers can
# override upward but not silently downward.
_AGENT_MIN_NUM_CTX = 8192


# ----- Run state --------------------------------------------------------------


@dataclass
class AgentRunResult:
    """Mutable result handed back to the calling endpoint after the loop.

    The endpoint reads this after the async generator completes to persist
    the assistant message + citations + tool-call audit.
    """

    final_content: str = ""
    rag_citations: Optional[Dict[str, Any]] = None
    tool_calls_audit: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    error: Optional[str] = None


# ----- Ollama HTTP client (bypassing the pinned 0.1.6 python client) ----------


async def _ollama_chat_nonstream(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    options: Optional[Dict[str, Any]],
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """POST /api/chat with stream=False and return the parsed JSON response."""
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        body["tools"] = tools
    if options:
        body["options"] = options

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=body,
        )
        response.raise_for_status()
        return response.json()


async def _ollama_chat_stream(
    model: str,
    messages: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]],
    timeout: float = 300.0,
) -> AsyncGenerator[str, None]:
    """POST /api/chat with stream=True, yielding `message.content` chunks.

    Used only for the final-answer pass once the model is done calling tools.
    Tools are intentionally NOT passed here — at this point we want the model
    to produce prose, not another tool call.
    """
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if options:
        body["options"] = options

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping malformed Ollama stream line: %s", line[:80]
                    )
                    continue
                msg = data.get("message", {})
                content = msg.get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    return


# ----- Tool dispatch ----------------------------------------------------------


async def _execute_search_wikipedia(
    args: Dict[str, Any],
    project: Project,
) -> Tuple[str, List[Dict[str, Any]], bool]:
    """
    Execute one search_wikipedia call.

    Returns (tool_text_for_model, deduped_hits, used_dense_flag).

    Raises ValueError on malformed args; the loop catches it and feeds the
    error message back to the model so it can self-correct on the next turn.
    """
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "Missing or empty 'query' argument (expected a non-empty string)."
        )

    capped_top_k = min(_TOOL_TOP_K_CAP, project.rag_top_k or _TOOL_TOP_K_CAP)

    raw = await rag_service.retrieve(
        base_url=project.rag_server_url,
        query=query.strip(),
        corpus=project.rag_corpus_id,
        top_k=capped_top_k,
    )
    raw_hits = raw.get("hits", []) or []
    deduped = dedupe_hits_by_page(raw_hits, keep_per_page=2)[:capped_top_k]
    used_dense = bool(raw.get("used_dense", False))

    tool_text = format_rag_context(
        {
            "corpus": project.rag_corpus_id,
            "hits": deduped,
        }
    )
    if not tool_text:
        tool_text = f"No results found for query: {query!r}"

    return tool_text, deduped, used_dense


# name -> (args, project) -> (tool_text, hits, used_dense)
TOOLS: Dict[str, Callable[..., Awaitable[Tuple[str, List[Dict[str, Any]], bool]]]] = {
    "search_wikipedia": _execute_search_wikipedia,
}


# ----- Agent loop -------------------------------------------------------------


def _agent_options(base_options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Adjust generation options for the agent loop (bump num_ctx)."""
    opts = dict(base_options or {})
    current_ctx = opts.get("num_ctx", 0) or 0
    opts["num_ctx"] = max(current_ctx, _AGENT_MIN_NUM_CTX)
    return opts


def _build_citations(
    server_base_url: str,
    corpus: str,
    article_url_template: str,
    aggregated_hits: List[Dict[str, Any]],
    used_dense_any: bool,
) -> Optional[Dict[str, Any]]:
    """Build the final messages.rag_citations payload from accumulated hits."""
    if not aggregated_hits:
        return None
    final = dedupe_hits_by_page(aggregated_hits, keep_per_page=2)
    return {
        "used_dense": used_dense_any,
        "corpus": corpus,
        "server_base_url": server_base_url,
        "article_url_template": article_url_template,
        "hits": [
            {
                "title": h.get("title", ""),
                "section": h.get("section"),
                "score": h.get("score", 0.0),
            }
            for h in final
        ],
    }


async def run_agent(
    model: str,
    initial_messages: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]],
    project: Project,
    result: AgentRunResult,
    is_disconnected: Callable[[], Awaitable[bool]],
    max_iters: int = 5,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Drive the agent loop and yield NDJSON frame dicts for the endpoint to
    serialize. Mutates `result` so the caller can persist final state.

    `initial_messages` should already include the chat history + the new user
    message. The agent prepends its own system prompt directive.
    """
    # Pre-flight: fetch /rag/info to get article_url_template for citations.
    try:
        info = await rag_service.get_info(project.rag_server_url)
    except Exception as e:
        msg = f"RAG server unavailable: {e}"
        logger.error(msg)
        result.error = msg
        yield {"type": "error", "message": msg}
        return
    article_url_template = info.get("article_url_template", "/article/{title}")

    # Prepend the agent system directive. If there's already a system message
    # from project custom instructions etc., this stacks on top of it.
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT}
    ] + list(initial_messages)
    agent_options = _agent_options(options)

    aggregated_hits: List[Dict[str, Any]] = []
    used_dense_any = False
    accumulated_text: List[str] = []

    def _commit_citations() -> None:
        result.rag_citations = _build_citations(
            server_base_url=project.rag_server_url,
            corpus=project.rag_corpus_id,
            article_url_template=article_url_template,
            aggregated_hits=aggregated_hits,
            used_dense_any=used_dense_any,
        )

    for iter_idx in range(max_iters):
        if await is_disconnected():
            logger.info("Agent loop: client disconnected before iteration %d", iter_idx)
            result.truncated = True
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            return

        # Tool-call detection pass: stream=False so we can inspect tool_calls.
        try:
            response = await _ollama_chat_nonstream(
                model=model,
                messages=messages,
                tools=[SEARCH_WIKIPEDIA_TOOL],
                options=agent_options,
            )
        except httpx.HTTPStatusError as e:
            err = f"Ollama returned {e.response.status_code}: {e.response.text[:200]}"
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

        msg = response.get("message", {}) or {}
        msg_content = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls", []) or []

        # Some models emit reasoning text alongside tool_calls. Surface it.
        if msg_content:
            yield {"type": "chunk", "content": msg_content}
            accumulated_text.append(msg_content)

        if not tool_calls:
            # Model is done with tools. If it returned content above, that IS
            # the final answer (already streamed as a chunk). If it returned
            # nothing, force a final streaming call with no tools.
            if not msg_content:
                try:
                    async for piece in _ollama_chat_stream(
                        model=model,
                        messages=messages,
                        options=agent_options,
                    ):
                        if await is_disconnected():
                            result.truncated = True
                            break
                        yield {"type": "chunk", "content": piece}
                        accumulated_text.append(piece)
                except Exception as e:
                    err = f"Final answer generation failed: {e}"
                    logger.error(err)
                    result.error = err
                    result.final_content = "".join(accumulated_text)
                    _commit_citations()
                    yield {"type": "error", "message": err}
                    return
            result.final_content = "".join(accumulated_text)
            _commit_citations()
            yield {"type": "done", "truncated": result.truncated}
            return

        # Record the assistant's tool-calling turn in the conversation so the
        # next iteration sees it. Ollama expects this shape on subsequent calls.
        messages.append(
            {
                "role": "assistant",
                "content": msg_content,
                "tool_calls": tool_calls,
            }
        )

        for tc in tool_calls:
            tc_id = uuid_lib.uuid4().hex[:12]
            fn = tc.get("function", {}) or {}
            tool_name = fn.get("name", "") or ""
            # Ollama returns arguments already parsed as a dict (unlike OpenAI's
            # JSON-string convention) — but be defensive in case a future Ollama
            # version changes this.
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    tool_input: Dict[str, Any] = json.loads(raw_args)
                except json.JSONDecodeError:
                    tool_input = {}
            else:
                tool_input = raw_args or {}

            yield {
                "type": "tool_call",
                "id": tc_id,
                "name": tool_name,
                "input": tool_input,
            }

            handler = TOOLS.get(tool_name)
            if handler is None:
                err_msg = f"Unknown tool: {tool_name}"
                yield {
                    "type": "tool_result",
                    "id": tc_id,
                    "ok": False,
                    "error": err_msg,
                }
                result.tool_calls_audit.append(
                    {
                        "id": tc_id,
                        "name": tool_name,
                        "input": tool_input,
                        "ok": False,
                        "error": err_msg,
                    }
                )
                messages.append({"role": "tool", "content": f"Tool error: {err_msg}"})
                continue

            try:
                tool_text, new_hits, used_dense = await handler(tool_input, project)
                aggregated_hits.extend(new_hits)
                used_dense_any = used_dense_any or used_dense
                summary = f"{len(new_hits)} result{'s' if len(new_hits) != 1 else ''}"
                yield {
                    "type": "tool_result",
                    "id": tc_id,
                    "ok": True,
                    "summary": summary,
                }
                result.tool_calls_audit.append(
                    {
                        "id": tc_id,
                        "name": tool_name,
                        "input": tool_input,
                        "ok": True,
                        "summary": summary,
                    }
                )
                messages.append({"role": "tool", "content": tool_text})
            except Exception as e:
                err_msg = str(e) or e.__class__.__name__
                logger.warning("Tool %s failed: %s", tool_name, err_msg)
                yield {
                    "type": "tool_result",
                    "id": tc_id,
                    "ok": False,
                    "error": err_msg,
                }
                result.tool_calls_audit.append(
                    {
                        "id": tc_id,
                        "name": tool_name,
                        "input": tool_input,
                        "ok": False,
                        "error": err_msg,
                    }
                )
                messages.append({"role": "tool", "content": f"Tool error: {err_msg}"})

    # Iteration cap hit — force a final answer with no tools available.
    logger.info("Agent loop hit iteration cap (%d); forcing final answer", max_iters)
    result.truncated = True
    try:
        async for piece in _ollama_chat_stream(
            model=model,
            messages=messages,
            options=agent_options,
        ):
            if await is_disconnected():
                break
            yield {"type": "chunk", "content": piece}
            accumulated_text.append(piece)
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
