/**
 * Streaming chat client (PLAN_NEW.md Phase 4).
 *
 * Replaces the previous EventSource + GET ?message=... setup with a
 * POST + fetch ReadableStream that consumes NDJSON. NDJSON framing means
 * one JSON object per `\n`-terminated line; the backend emits three
 * frame shapes:
 *
 *   { type: "chunk", content: string }
 *   { type: "done",  truncated: boolean }
 *   { type: "error", message: string }
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type ChunkFrame = { type: 'chunk'; content: string }
export type DoneFrame = { type: 'done'; truncated: boolean }
export type ErrorFrame = { type: 'error'; message: string }
export type StreamFrame = ChunkFrame | DoneFrame | ErrorFrame

export interface StreamMessageRequest {
  content: string
  file_ids?: string[] | null
}

/**
 * Open a stream for `POST /api/v1/chats/{chatId}/stream` and yield each
 * NDJSON frame as it arrives. The returned generator can be cancelled by
 * aborting `controller`; abort propagates as a `DOMException` named
 * `AbortError`, which the caller is expected to swallow.
 */
export async function* streamChat(
  chatId: string,
  body: StreamMessageRequest,
  controller: AbortController
): AsyncGenerator<StreamFrame, void, void> {
  const url = `${API_URL}/api/v1/chats/${chatId}/stream`

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
    // Always release the reader so the underlying connection can be GC'd.
    try {
      reader.releaseLock()
    } catch {
      /* already released */
    }
  }
}
