/**
 * Streaming store — owns the in-flight chat stream OUTSIDE the React
 * component tree so navigating away from the chat page does not abort it.
 *
 * `useStreaming` (the hook) is a thin facade over this store; it used to
 * own the state itself, which meant unmounting `ChatContainer` (e.g. when
 * the user clicked Settings while the AI was mid-response) aborted the
 * fetch and threw away the partial output. Now the fetch lives here and
 * keeps streaming; when the user navigates back, `ChatContainer` re-reads
 * `streamingContent` for its `activeChatId` and the response is still
 * there.
 *
 * Single-stream guarantee is preserved: a second `startStream` while one
 * is in flight is rejected with `error` set.
 */
import { create } from 'zustand'
import { streamChat, type StreamFrame } from '@/services/streamApi'
import { chatApi } from '@/services/chatApi'
import { useChatStore } from './chatStore'

interface StreamingStore {
  activeChatId: string | null
  isStreaming: boolean
  streamingContent: string
  error: string | null

  startStream: (
    chatId: string,
    message: string,
    fileIds: string[] | null
  ) => Promise<void>
  cancelStream: () => void
  clearError: () => void
}

// Module-level so cancelStream can reach across the store boundary without
// stashing the controller in Zustand state (where it would trigger spurious
// re-renders on subscribers).
let controller: AbortController | null = null

export const useStreamingStore = create<StreamingStore>((set) => ({
  activeChatId: null,
  isStreaming: false,
  streamingContent: '',
  error: null,

  clearError: () => set({ error: null }),

  cancelStream: () => {
    controller?.abort()
    controller = null
    set({ isStreaming: false, activeChatId: null, streamingContent: '' })
  },

  startStream: async (chatId, message, fileIds) => {
    if (controller) {
      set({ error: 'A message is already streaming.' })
      return
    }

    const ctrl = new AbortController()
    controller = ctrl

    set({
      activeChatId: chatId,
      isStreaming: true,
      streamingContent: '',
      error: null,
    })

    let accumulated = ''
    let terminalError: string | null = null

    try {
      for await (const frame of streamChat(
        chatId,
        { content: message, file_ids: fileIds },
        ctrl
      ) as AsyncGenerator<StreamFrame, void, void>) {
        if (frame.type === 'chunk') {
          accumulated += frame.content
          set({ streamingContent: accumulated })
        } else if (frame.type === 'done') {
          break
        } else if (frame.type === 'error') {
          terminalError = frame.message
          break
        }
      }
    } catch (err) {
      // AbortError is expected on user cancel — don't surface it.
      if ((err as Error)?.name !== 'AbortError') {
        terminalError = (err as Error)?.message ?? 'Streaming failed'
      }
    }

    if (controller === ctrl) {
      controller = null
    }

    if (terminalError) {
      set({
        isStreaming: false,
        activeChatId: null,
        streamingContent: '',
        error: terminalError,
      })
      return
    }

    // Refetch and commit BEFORE clearing the streaming bubble, otherwise
    // there is a brief window where the bubble is gone but the persisted
    // assistant message hasn't landed in chatStore yet, causing a flicker.
    // Only commit if the user is still looking at this chat; otherwise the
    // next time they navigate back, `ChatContainer`'s effect refetches.
    try {
      const updatedChat = await chatApi.get(chatId)
      const current = useChatStore.getState().currentChat
      if (current?.id === chatId) {
        useChatStore.setState({
          currentChat: updatedChat,
          messages: updatedChat.messages,
        })
      }
    } catch {
      /* ignore — next mount will refetch */
    }

    set({ isStreaming: false, activeChatId: null, streamingContent: '' })
  },
}))
