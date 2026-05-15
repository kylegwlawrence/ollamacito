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

from ollama import ResponseError

from app.core.logging import get_logger
from app.db.models import Project
from app.services.ollama_service import ollama_service
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
    "a local Wikipedia knowledge base.\n\n"
    "When NOT to call the tool: greetings, thanks, acknowledgements, small talk, "
    "opinions, clarifying questions, or any message that doesn't name a specific "
    "factual topic to look up. Answer those directly without invoking any tool.\n\n"
    "When to call the tool: the user asks about a specific person, place, event, "
    "concept, or fact you may not know. The query must be a substantive non-empty "
    "string focused on key entities — never call the tool with an empty query.\n\n"
    "When you do search, cite sources inline by their bracketed title "
    "(e.g. `[French Revolution § Causes]`). At most a few search calls per turn — "
    "be efficient."
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

    server = project.rag_server
    if server is None:
        raise ValueError(
            "Project has no RAG server configured (rag_server relationship is None)."
        )

    raw = await rag_service.retrieve(
        base_url=server.url,
        query=query.strip(),
        corpus=server.corpus_id,
        top_k=capped_top_k,
    )
    raw_hits = raw.get("hits", []) or []
    deduped = dedupe_hits_by_page(raw_hits, keep_per_page=2)[:capped_top_k]
    used_dense = bool(raw.get("used_dense", False))

    tool_text = format_rag_context(
        {
            "corpus": server.corpus_id,
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


def _prevalidate_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable reason to suppress this tool_call, or None.

    Catches obviously degenerate calls (e.g. empty-query search) so we don't
    flash a useless tool_call frame in the UI. The model still receives the
    error back through a tool message and can self-correct.
    """
    if tool_name == "search_wikipedia":
        query = tool_input.get("query")
        if not isinstance(query, str) or not query.strip():
            return (
                "Empty or missing 'query' — do not call search_wikipedia for "
                "conversational input, greetings, or small talk. Answer directly."
            )
    return None


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


def _parse_tool_call(tc: Any) -> Optional[Dict[str, Any]]:
    """Normalize one ollama-python ToolCall into the loop's dict shape.

    Returns None if the call has no function payload. `arguments` may arrive
    as Mapping (current client), str (older / future fallback), or None.
    """
    fn = getattr(tc, "function", None)
    if fn is None:
        return None
    name = getattr(fn, "name", "") or ""
    raw_args = getattr(fn, "arguments", None)
    if isinstance(raw_args, str):
        try:
            parsed: Dict[str, Any] = json.loads(raw_args)
        except json.JSONDecodeError:
            parsed = {}
    elif raw_args is None:
        parsed = {}
    else:
        parsed = dict(raw_args)
    return {"function": {"name": name, "arguments": parsed}}


async def run_agent(
    model: str,
    initial_messages: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]],
    project: Project,
    result: AgentRunResult,
    is_disconnected: Callable[[], Awaitable[bool]],
    max_iters: int = 5,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Drive the agent loop and yield NDJSON frame dicts for the endpoint to
    serialize. Mutates `result` so the caller can persist final state.

    `initial_messages` should already include the chat history + the new user
    message. The agent prepends its own system prompt directive.

    Pass `system_prompt` to replace the default chat-agent directive (used by
    the course-generator pipeline to instruct the model to gather research
    notes instead of answering a chat turn).
    """
    # Pre-flight: fetch /rag/info to get article_url_template for citations.
    server = project.rag_server
    if server is None:
        msg = "Project has no RAG server configured."
        logger.error(msg)
        result.error = msg
        yield {"type": "error", "message": msg}
        return
    try:
        info = await rag_service.get_info(server.url)
    except Exception as e:
        msg = f"RAG server unavailable: {e}"
        logger.error(msg)
        result.error = msg
        yield {"type": "error", "message": msg}
        return
    article_url_template = info.get("article_url_template", "/article/{title}")

    # Prepend the agent system directive. If there's already a system message
    # from project custom instructions etc., this stacks on top of it. Callers
    # may override the default directive (course generator does this for its
    # research-notes phase).
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt or AGENT_SYSTEM_PROMPT}
    ] + list(initial_messages)
    agent_options = _agent_options(options)

    aggregated_hits: List[Dict[str, Any]] = []
    used_dense_any = False
    accumulated_text: List[str] = []

    def _commit_citations() -> None:
        result.rag_citations = _build_citations(
            server_base_url=server.url,
            corpus=server.corpus_id,
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
                    # Keep result.final_content current on every chunk so the
                    # endpoint's `finally` can persist whatever streamed so far
                    # even if cancellation fires before normal exit points.
                    result.final_content = "".join(accumulated_text)

                for tc in getattr(msg, "tool_calls", None) or []:
                    parsed = _parse_tool_call(tc)
                    if parsed is not None:
                        turn_tool_calls.append(parsed)
        except ResponseError as e:
            # Preserve today's HTTP-status granularity (was httpx.HTTPStatusError).
            status_code = getattr(e, "status_code", "?")
            body = str(getattr(e, "error", e))[:200]
            err = f"Ollama returned {status_code}: {body}"
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
            # fall back to one tool-free streaming call. Some tool-aware models
            # emit an empty turn when given tools but answer normally when
            # tools are absent — this preserves the prior code's safety net.
            if not turn_content_parts:
                try:
                    fallback_stream = await ollama_service.client.chat(
                        model=model,
                        messages=messages,
                        options=agent_options,  # no tools= -> prose only
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
                            result.final_content = "".join(accumulated_text)
                except Exception as e:
                    err = f"Empty-turn fallback failed: {e}"
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
        # next iteration sees it.
        messages.append(
            {
                "role": "assistant",
                "content": "".join(turn_content_parts),
                "tool_calls": turn_tool_calls,
            }
        )

        for tc in turn_tool_calls:
            tc_id = uuid_lib.uuid4().hex[:12]
            fn = tc.get("function", {}) or {}
            tool_name = fn.get("name", "") or ""
            tool_input: Dict[str, Any] = fn.get("arguments", {}) or {}

            # Pre-dispatch validation: silently reject obviously degenerate
            # calls (e.g. empty-query search) without emitting a tool_call
            # frame to the UI. The model still gets a tool message back so it
            # can self-correct on the next iteration.
            skip_reason = _prevalidate_tool_call(tool_name, tool_input)
            if skip_reason is not None:
                logger.info(
                    "Suppressed degenerate tool_call (%s): %s", tool_name, skip_reason
                )
                result.tool_calls_audit.append(
                    {
                        "id": tc_id,
                        "name": tool_name,
                        "input": tool_input,
                        "ok": False,
                        "error": skip_reason,
                        "suppressed": True,
                    }
                )
                messages.append(
                    {"role": "tool", "content": f"Tool error: {skip_reason}"}
                )
                continue

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
        stream = await ollama_service.client.chat(
            model=model,
            messages=messages,
            options=agent_options,  # no tools= -> prose only
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
                result.final_content = "".join(accumulated_text)
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
