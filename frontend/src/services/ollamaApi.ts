import api from './api'
import type { OllamaModelListResponse, OllamaStatusResponse } from '@/types'

export const ollamaApi = {
  listModels: async (serverId?: string | null): Promise<OllamaModelListResponse> => {
    const params = serverId ? { server_id: serverId } : {}
    const { data } = await api.get('/ollama/models', { params })
    return data
  },

  checkStatus: async (): Promise<OllamaStatusResponse> => {
    const { data } = await api.get('/ollama/status')
    return data
  },
}
