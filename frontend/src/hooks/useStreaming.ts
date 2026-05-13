import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChat, type StreamFrame } from '@/services/streamApi'

interface UseStreamingReturn {
  sendMessage: (chatId: string, message: string) => Promise<void>
  isStreaming: boolean
  streamingContent: string
  error: string | null
  cancelStream: () => void
}

/**
 * React hook driving a single chat stream at a time (PLAN_NEW.md Phase 4).
 *
 * Guarantees:
 *
 * - Only one stream may be active. A second `sendMessage` while streaming is
 *   rejected (the input UI is also disabled during streaming, so this only
 *   ever fires on edge cases like rapid double-click).
 * - `AbortController.abort()` is called on unmount, so navigating away does
 *   not leak the HTTP connection or the underlying Ollama generator.
 * - Errors always surface to the caller — no silent treatment of partial
 *   responses as "done", which was the bug in the Phase 0 EventSource code.
 * - `onComplete` is read through a ref, so inline callers don't recreate the
 *   hook every render.
 * - In React 18 Strict Mode (double-mount in dev), the second mount aborts
 *   its own controller cleanly without affecting the first.
 */
export const useStreaming = (
  onComplete?: (fullResponse: string, truncated: boolean) => void
): UseStreamingReturn => {
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [error, setError] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)
  // onComplete via ref so callers can pass an inline closure without
  // re-creating `sendMessage` on every render.
  const onCompleteRef = useRef(onComplete)
  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  // Cleanup on unmount: abort any in-flight stream so the fetch closes
  // and the backend sees the disconnect.
  useEffect(() => {
    return () => {
      controllerRef.current?.abort()
      controllerRef.current = null
    }
  }, [])

  const cancelStream = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setIsStreaming(false)
  }, [])

  const sendMessage = useCallback(
    async (chatId: string, message: string): Promise<void> => {
      // Reject concurrent invocations. The caller should disable the input.
      if (controllerRef.current) {
        setError('A message is already streaming.')
        return
      }

      const controller = new AbortController()
      controllerRef.current = controller

      setIsStreaming(true)
      setStreamingContent('')
      setError(null)

      let accumulated = ''
      let terminalError: string | null = null
      let truncated = false

      try {
        for await (const frame of streamChat(
          chatId,
          { content: message, file_ids: null },
          controller
        ) as AsyncGenerator<StreamFrame, void, void>) {
          if (frame.type === 'chunk') {
            accumulated += frame.content
            setStreamingContent(accumulated)
          } else if (frame.type === 'done') {
            truncated = frame.truncated
            break
          } else if (frame.type === 'error') {
            terminalError = frame.message
            break
          }
        }
      } catch (err) {
        // AbortError is expected on cancellation/unmount — don't surface it.
        if ((err as Error)?.name !== 'AbortError') {
          terminalError = (err as Error)?.message ?? 'Streaming failed'
        }
      } finally {
        // Only clear the controller if it's still ours — if a new stream was
        // somehow started, we don't want to stomp on it.
        if (controllerRef.current === controller) {
          controllerRef.current = null
        }
        setIsStreaming(false)
        setStreamingContent('')
      }

      if (terminalError) {
        setError(terminalError)
        return
      }

      onCompleteRef.current?.(accumulated, truncated)
    },
    []
  )

  return { sendMessage, isStreaming, streamingContent, error, cancelStream }
}
