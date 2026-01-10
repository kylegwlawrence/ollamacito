import api from './api'
import type { Chat, ChatCreate, ChatUpdate, ChatListResponse, ChatWithMessages } from '@/types'

export const chatApi = {
  list: async (page = 1, pageSize = 20, includeArchived = false): Promise<ChatListResponse> => {
    const { data } = await api.get('/chats', {
      params: { page, page_size: pageSize, include_archived: includeArchived },
    })
    return data
  },

  get: async (chatId: string): Promise<ChatWithMessages> => {
    const { data } = await api.get(`/chats/${chatId}`)
    return data
  },

  create: async (chatData: ChatCreate): Promise<Chat> => {
    const { data } = await api.post('/chats', chatData)
    return data
  },

  update: async (chatId: string, chatData: ChatUpdate): Promise<Chat> => {
    const { data } = await api.patch(`/chats/${chatId}`, chatData)
    return data
  },

  delete: async (chatId: string): Promise<void> => {
    await api.delete(`/chats/${chatId}`)
  },

  archive: async (chatId: string): Promise<Chat> => {
    const { data } = await api.post(`/chats/${chatId}/archive`)
    return data
  },
}
