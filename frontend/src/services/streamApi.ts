/**
 * Streaming chat client (PLAN_NEW.md Phase 4) + agentic variant.
 *
 * Two endpoints share the same NDJSON wire format:
 *   POST /api/v1/chats/{id}/stream   — regular chat
 *   POST /api/v1/chats/{id}/agent    — agentic chat with search_wikipedia tool
 *
 * NDJSON: one JSON object per `\n`-terminated line. Frame types:
 *   { type: "chunk",       content: string }
 *   { type: "done",        truncated: boolean }
 *   { type: "error",       message: string }
 *   { type: "tool_call",   id: string, name: string, input: object } // agent only
 *   { type: "tool_result", id: string, ok: boolean, summary?: string, error?: string } // agent only
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type ChunkFrame = { type: 'chunk'; content: string }
export type DoneFrame = { type: 'done'; truncated: boolean }
export type ErrorFrame = { type: 'error'; message: string }
export type ToolCallFrame = {
  type: 'tool_call'
  id: string
  name: string
  input: Record<string, unknown>
}
export type ToolResultFrame = {
  type: 'tool_result'
  id: string
  ok: boolean
  summary?: string
  error?: string
}
export type StreamFrame =
  | ChunkFrame
  | DoneFrame
  | ErrorFrame
  | ToolCallFrame
  | ToolResultFrame

export interface StreamMessageRequest {
  content: string
  file_ids?: string[] | null
}

/**
 * Core NDJSON-parsing generator shared by `streamChat` and `streamAgent`.
 * POSTs the body, reads `response.body` as a stream of UTF-8 bytes, and
 * yields each parsed JSON frame as it arrives. Frame-type-agnostic.
 */
async function* streamNdjson(
  url: string,
  body: StreamMessageRequest,
  controller: AbortController
): AsyncGenerator<StreamFrame, void, void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
    credentials: 'include',
  })

  if (!response.ok) {
    // Non-200 = the request never started streaming (auth, validation, 5xx
    // before the generator yielded anything). Surface a single error frame
    // so the caller has one shape to handle.
    const text = await response.text().catch(() => '')
    yield {
      type: 'error',
      message: `HTTP ${response.status}: ${text || response.statusText}`,
    }
    return
  }

  if (!response.body) {
    yield { type: 'error', message: 'Stream response has no body' }
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Split on `\n`, keep the trailing partial line in the buffer.
      let nl: number
      while ((nl = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, nl).trim()
        buffer = buffer.slice(nl + 1)
        if (!line) continue
        try {
          yield JSON.parse(line) as StreamFrame
        } catch (e) {
          yield { type: 'error', message: `Malformed NDJSON frame: ${line}` }
          return
        }
      }
    }
    // Flush any trailing line without a newline (some servers omit final \n).
    const tail = buffer.trim()
    if (tail) {
      try {
        yield JSON.parse(tail) as StreamFrame
      } catch {
        yield { type: 'error', message: `Malformed NDJSON tail: ${tail}` }
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* already released */
    }
  }
}

/**
 * Open a stream for `POST /api/v1/chats/{chatId}/stream`.
 */
export function streamChat(
  chatId: string,
  body: StreamMessageRequest,
  controller: AbortController
): AsyncGenerator<StreamFrame, void, void> {
  return streamNdjson(
    `${API_URL}/api/v1/chats/${chatId}/stream`,
    body,
    controller
  )
}

/**
 * Open a stream for `POST /api/v1/chats/{chatId}/agent` — same NDJSON
 * transport as streamChat, but the model has tool access.
 */
export function streamAgent(
  chatId: string,
  body: StreamMessageRequest,
  controller: AbortController
): AsyncGenerator<StreamFrame, void, void> {
  return streamNdjson(
    `${API_URL}/api/v1/chats/${chatId}/agent`,
    body,
    controller
  )
}
