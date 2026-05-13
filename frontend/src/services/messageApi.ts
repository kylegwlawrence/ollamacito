import api from './api'
import type { Message, MessageCreate, MessageListResponse } from '@/types'

// Streaming lives in `streamApi.ts` (POST + fetch ReadableStream); the
// previous GET ?message=... URL-builder was removed in Phase 4.
export const messageApi = {
  list: async (chatId: string, page = 1, pageSize = 50): Promise<MessageListResponse> => {
    const { data } = await api.get(`/chats/${chatId}/messages`, {
      params: { page, page_size: pageSize },
    })
    return data
  },

  create: async (chatId: string, messageData: MessageCreate): Promise<Message> => {
    const { data } = await api.post(`/chats/${chatId}/messages`, messageData)
    return data
  },
}
