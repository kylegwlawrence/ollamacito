export interface AttachedFileInfo {
  id: string
  filename: string
  file_type: string
  file_size: number
}

export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
  ok: boolean
  summary?: string
  error?: string
}

export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens_used?: number
  attached_files?: AttachedFileInfo[]
  rag_citations?: RagCitations | null
  tool_calls?: ToolCall[] | null
  created_at: string
}

export interface RagCitationHit {
  title: string
  section: string | null
  score: number
}

export interface RagCitations {
  used_dense: boolean
  corpus: string
  server_base_url: string
  article_url_template: string
  hits: RagCitationHit[]
}

export interface MessageCreate {
  content: string
  file_ids?: string[]
}

export interface MessageListResponse {
  messages: Message[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface StreamChunk {
  content: string
  done: boolean
}

export interface StreamError {
  error: string
  detail?: string
}
