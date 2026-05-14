import api from './api'
import type { RagInfo } from '@/types'

export const ragApi = {
  /**
   * Test connectivity to a RAG server by proxying GET /rag/info through the backend.
   *
   * The backend takes the URL from the body (not the project's stored URL) so
   * the user can validate before saving. Failures surface as 503 / 422 via the
   * RAG exception handlers in main.py.
   */
  testConnection: async (
    projectId: string,
    ragServerUrl: string
  ): Promise<RagInfo> => {
    const { data } = await api.post(`/projects/${projectId}/rag/info`, {
      rag_server_url: ragServerUrl,
    })
    return data
  },
}
