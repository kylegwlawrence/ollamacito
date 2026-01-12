export interface AttachedFileInfo {
  id: string
  filename: string
  file_type: string
  file_size: number
}

export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens_used?: number
  attached_files?: AttachedFileInfo[]
  created_at: string
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
