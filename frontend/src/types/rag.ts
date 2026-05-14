/**
 * Types mirroring the local-Wikipedia RAG server's wire contract.
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
