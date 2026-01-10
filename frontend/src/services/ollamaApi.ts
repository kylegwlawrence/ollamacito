import api from './api'
import type { OllamaModelListResponse, OllamaStatusResponse } from '@/types'

export const ollamaApi = {
  listModels: async (): Promise<OllamaModelListResponse> => {
    const { data } = await api.get('/ollama/models')
    return data
  },

  checkStatus: async (): Promise<OllamaStatusResponse> => {
    const { data } = await api.get('/ollama/status')
    return data
  },
}
