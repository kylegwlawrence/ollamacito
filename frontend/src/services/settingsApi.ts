import api from './api'
import type { Settings, SettingsUpdate, ChatSettings, ChatSettingsUpdate } from '@/types'

export const settingsApi = {
  getGlobal: async (): Promise<Settings> => {
    const { data } = await api.get('/settings')
    return data
  },

  updateGlobal: async (settingsData: SettingsUpdate): Promise<Settings> => {
    const { data } = await api.patch('/settings', settingsData)
    return data
  },

  getChat: async (chatId: string): Promise<ChatSettings> => {
    const { data } = await api.get(`/chats/${chatId}/settings`)
    return data
  },

  updateChat: async (chatId: string, settingsData: ChatSettingsUpdate): Promise<ChatSettings> => {
    const { data } = await api.patch(`/chats/${chatId}/settings`, settingsData)
    return data
  },
}
