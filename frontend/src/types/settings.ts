export interface Settings {
  id: number
  default_model: string
  conversation_summarization_model: string
  default_temperature: number
  default_max_tokens: number
  num_ctx: number
  theme: 'dark' | 'light'
  created_at: string
  updated_at: string
}

export interface SettingsUpdate {
  default_model?: string
  conversation_summarization_model?: string
  default_temperature?: number
  default_max_tokens?: number
  num_ctx?: number
  theme?: 'dark' | 'light'
}

export interface ChatSettings {
  chat_id: string
  temperature?: number | null
  max_tokens?: number | null
  system_prompt?: string | null
  created_at: string
  updated_at: string
}

export interface ChatSettingsUpdate {
  temperature?: number | null
  max_tokens?: number | null
  system_prompt?: string | null
}
