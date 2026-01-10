import api from './api'
import type { Message, MessageCreate, MessageListResponse } from '@/types'

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

  // Streaming endpoint URL generator
  getStreamUrl: (chatId: string, message: string): string => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const encodedMessage = encodeURIComponent(message)
    return `${baseUrl}/api/v1/chats/${chatId}/stream?message=${encodedMessage}`
  },
}
