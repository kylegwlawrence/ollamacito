/**
 * Types mirroring the local-Wikipedia RAG server's wire contract and the
 * user-owned RAG server entries persisted by the backend.
 * See LOCAL_WIKIPEDIA_API.md.
 */

export interface RagCorpusInfo {
  id: string
  display_name: string
  article_count: number
}

export interface RagInfo {
  server_name: string
  server_version: string
  description: string
  embedding_model: string
  embedding_dim: number
  default_top_k: number
  max_top_k: number
  article_url_template: string
  corpora: RagCorpusInfo[]
}

/** A user-owned saved (name, url, corpus_id) entry. */
export interface RagServer {
  id: string
  name: string
  url: string
  corpus_id: string
  created_at: string
  updated_at: string
}

export interface RagServerListResponse {
  servers: RagServer[]
}

export interface RagServerCreate {
  name: string
  url: string
  corpus_id: string
}

export interface RagServerUpdate {
  name?: string
  url?: string
  corpus_id?: string
}

export interface RagServerTestRequest {
  url: string
  corpus_id: string
}

export interface RagServerTestResult {
  server_name: string | null
  server_version: string | null
  description: string | null
  embedding_model: string | null
  embedding_dim: number | null
  default_top_k: number | null
  max_top_k: number | null
  article_url_template: string | null
  available_corpora: string[]
  corpus_found: boolean
}
