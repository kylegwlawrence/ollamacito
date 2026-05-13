/**
 * Chat store (PLAN_NEW.md Phase 5+6).
 *
 * Replaces ChatContext. Holds the chat the user is currently viewing, its
 * in-memory messages, and the per-message file-selection state for Phase 6.
 * The dead `isStreaming` / `streamingContent` fields from the old
 * ChatContext are gone — `useStreaming` owns that state locally.
 */
import { create } from 'zustand'
import type { Chat, Message } from '@/types'

interface ChatStore {
  currentChat: Chat | null
  messages: Message[]
  // Project file IDs the user has chosen to attach to the next message.
  // Reset when currentChat changes (the ChatContainer does that).
  selectedFileIds: string[]
  setCurrentChat: (chat: Chat | null) => void
  setMessages: (messages: Message[]) => void
  setSelectedFileIds: (ids: string[]) => void
  toggleFileId: (id: string) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  currentChat: null,
  messages: [],
  selectedFileIds: [],
  setCurrentChat: (chat) => set({ currentChat: chat }),
  setMessages: (messages) => set({ messages }),
  setSelectedFileIds: (ids) => set({ selectedFileIds: ids }),
  toggleFileId: (id) =>
    set((s) => ({
      selectedFileIds: s.selectedFileIds.includes(id)
        ? s.selectedFileIds.filter((x) => x !== id)
        : [...s.selectedFileIds, id],
    })),
}))
