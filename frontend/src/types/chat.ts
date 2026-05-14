import type { Message } from './message'

export interface Chat {
  id: string
  title: string
  model: string
  is_archived: boolean
  project_id?: string | null
  agent_mode_enabled: boolean
  created_at: string
  updated_at: string
  message_count?: number
}

export interface ChatCreate {
  title: string
  model: string
  project_id?: string | null
  agent_mode_enabled?: boolean
}

export interface ChatUpdate {
  title?: string
  model?: string
  is_archived?: boolean
  agent_mode_enabled?: boolean
}

export interface ChatWithMessages extends Chat {
  messages: Message[]
}

export interface ChatListResponse {
  chats: Chat[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
