import { useCallback } from 'react'
import { useStreamingStore } from '@/stores/streamingStore'

interface UseStreamingReturn {
  sendMessage: (
    chatId: string,
    message: string,
    fileIds?: string[]
  ) => Promise<void>
  isStreaming: boolean
  streamingContent: string
  error: string | null
  cancelStream: () => void
  /** chatId whose stream is currently in-flight, or null. Lets callers
   *  decide whether the streaming bubble belongs on their page. */
  activeChatId: string | null
}

/**
 * Hook facade over `useStreamingStore`. The store owns the in-flight
 * fetch + accumulated content so the stream survives across navigation:
 * clicking away from a chat mid-response no longer aborts the stream,
 * and coming back picks up exactly where you left off (PLAN_NEW.md Phase 4
 * extended for the "AI response disappears" bug).
 *
 * Single-stream guarantee is preserved by the store (a second send while
 * one is in-flight is rejected with `error` set). Cancel is still wired
 * to the Stop button in `MessageInput`.
 */
export const useStreaming = (): UseStreamingReturn => {
  const isStreaming = useStreamingStore((s) => s.isStreaming)
  const streamingContent = useStreamingStore((s) => s.streamingContent)
  const error = useStreamingStore((s) => s.error)
  const activeChatId = useStreamingStore((s) => s.activeChatId)
  const startStream = useStreamingStore((s) => s.startStream)
  const cancelStream = useStreamingStore((s) => s.cancelStream)

  const sendMessage = useCallback(
    (chatId: string, message: string, fileIds?: string[]) =>
      startStream(chatId, message, fileIds ?? null),
    [startStream]
  )

  return {
    sendMessage,
    isStreaming,
    streamingContent,
    error,
    cancelStream,
    activeChatId,
  }
}
