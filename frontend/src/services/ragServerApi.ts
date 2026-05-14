import api from './api'
import type {
  RagServer,
  RagServerCreate,
  RagServerListResponse,
  RagServerTestRequest,
  RagServerTestResult,
  RagServerUpdate,
} from '@/types'

/**
 * Client for /api/v1/rag-servers — user-owned saved RAG server entries.
 *
 * Each entry is one (name, url, corpus_id) tuple. Projects reference an
 * entry by `rag_server_id` instead of carrying URL + corpus inline.
 */
export const ragServerApi = {
  list: async (): Promise<RagServer[]> => {
    const { data } = await api.get<RagServerListResponse>('/rag-servers')
    return data.servers
  },

  create: async (body: RagServerCreate): Promise<RagServer> => {
    const { data } = await api.post<RagServer>('/rag-servers', body)
    return data
  },

  update: async (id: string, body: RagServerUpdate): Promise<RagServer> => {
    const { data } = await api.patch<RagServer>(`/rag-servers/${id}`, body)
    return data
  },

  remove: async (id: string): Promise<void> => {
    await api.delete(`/rag-servers/${id}`)
  },

  /**
   * Test a (url, corpus_id) pair against the live RAG server. Returns the
   * server's /rag/info payload plus a `corpus_found` flag. Connection
   * failures surface as 503 via the RAG exception handlers.
   */
  test: async (body: RagServerTestRequest): Promise<RagServerTestResult> => {
    const { data } = await api.post<RagServerTestResult>(
      '/rag-servers/test',
      body,
    )
    return data
  },
}
