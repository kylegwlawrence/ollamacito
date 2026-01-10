export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens_used?: number
  created_at: string
}

export interface MessageCreate {
  content: string
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
