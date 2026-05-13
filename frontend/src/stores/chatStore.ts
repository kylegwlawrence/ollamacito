/**
 * Chat store (PLAN_NEW.md Phase 5).
 *
 * Replaces ChatContext. Holds the chat the user is currently viewing and
 * its in-memory messages. The dead `isStreaming` / `streamingContent`
 * fields from the old ChatContext are gone — `useStreaming` owns that
 * state locally, the source of truth for the stream is the hook.
 */
import { create } from 'zustand'
import type { Chat, Message } from '@/types'

interface ChatStore {
  currentChat: Chat | null
  messages: Message[]
  setCurrentChat: (chat: Chat | null) => void
  setMessages: (messages: Message[]) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  currentChat: null,
  messages: [],
  setCurrentChat: (chat) => set({ currentChat: chat }),
  setMessages: (messages) => set({ messages }),
}))
