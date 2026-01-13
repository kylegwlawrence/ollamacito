/**
 * TypeScript types for Ollama server management
 */

export type ServerStatus = 'online' | 'offline' | 'unknown' | 'error'

export interface OllamaServer {
  id: string
  name: string
  tailscale_url: string
  description: string | null
  is_active: boolean
  status: ServerStatus
  last_checked_at: string | null
  last_error: string | null
  models_count: number
  average_response_time_ms: number | null
  created_at: string
  updated_at: string
}

export interface OllamaServerCreate {
  name: string
  tailscale_url: string
  description?: string | null
  is_active?: boolean
}

export interface OllamaServerUpdate {
  name?: string
  tailscale_url?: string
  description?: string | null
  is_active?: boolean
}

export interface OllamaServerListResponse {
  servers: OllamaServer[]
}
