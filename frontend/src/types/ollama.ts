export interface OllamaModel {
  name: string
  size?: number
  digest?: string
  modified_at?: string
}

export interface OllamaModelListResponse {
  models: OllamaModel[]
}

export interface OllamaStatusResponse {
  connected: boolean
  url: string
  models_count?: number
  error?: string
}
