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
 *
 * Agent mode: the same store handles agentic streams (which add `tool_call`
 * and `tool_result` frame types). When agentMode=true, `streamAgent` is
 * used in place of `streamChat`. In-flight tool calls accumulate in
 * `streamingToolCalls` for the UI to render between the user message and
 * the streaming answer bubble.
 */
import { create } from 'zustand'
import {
  streamChat,
  streamAgent,
  type StreamFrame,
} from '@/services/streamApi'
import { chatApi } from '@/services/chatApi'
import type { ToolCall } from '@/types/message'
import { useChatStore } from './chatStore'

interface StreamingStore {
  activeChatId: string | null
  isStreaming: boolean
  streamingContent: string
  streamingToolCalls: ToolCall[]
  error: string | null

  startStream: (
    chatId: string,
    message: string,
    fileIds: string[] | null,
    agentMode?: boolean
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
  streamingToolCalls: [],
  error: null,

  clearError: () => set({ error: null }),

  cancelStream: () => {
    controller?.abort()
    controller = null
    set({
      isStreaming: false,
      activeChatId: null,
      streamingContent: '',
      streamingToolCalls: [],
    })
  },

  startStream: async (chatId, message, fileIds, agentMode = false) => {
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
      streamingToolCalls: [],
      error: null,
    })

    let accumulated = ''
    const toolCalls: ToolCall[] = []
    let terminalError: string | null = null

    const streamFn = agentMode ? streamAgent : streamChat

    try {
      for await (const frame of streamFn(
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
        } else if (frame.type === 'tool_call') {
          toolCalls.push({
            id: frame.id,
            name: frame.name,
            input: frame.input,
            ok: false, // pending until the matching tool_result lands
          })
          set({ streamingToolCalls: [...toolCalls] })
        } else if (frame.type === 'tool_result') {
          const idx = toolCalls.findIndex((tc) => tc.id === frame.id)
          if (idx !== -1) {
            toolCalls[idx] = {
              ...toolCalls[idx],
              ok: frame.ok,
              summary: frame.summary,
              error: frame.error,
            }
            set({ streamingToolCalls: [...toolCalls] })
          }
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
        streamingToolCalls: [],
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

    set({
      isStreaming: false,
      activeChatId: null,
      streamingContent: '',
      streamingToolCalls: [],
    })
  },
}))
