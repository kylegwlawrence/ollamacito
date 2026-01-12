/**
 * Project-related TypeScript types.
 */

export interface Project {
  id: string
  name: string
  custom_instructions: string | null
  is_archived: boolean
  default_model?: string | null
  temperature?: number | null
  max_tokens?: number | null
  created_at: string
  updated_at: string
}

export interface ProjectFile {
  id: string
  project_id: string
  filename: string
  file_path: string
  file_type: string
  file_size: number
  content_preview: string | null
  content?: string | null
  created_at: string
}

export interface ProjectFileCreate {
  filename: string
  file_type: 'txt' | 'json' | 'csv'
  content: string
}

export interface ProjectResponse extends Project {
  chat_count: number
  file_count: number
}

export interface ProjectWithDetails extends ProjectResponse {
  files: ProjectFile[]
}

export interface ProjectCreate {
  name: string
  custom_instructions?: string
  default_model?: string
  temperature?: number
  max_tokens?: number
}

export interface ProjectUpdate {
  name?: string
  custom_instructions?: string
  is_archived?: boolean
  default_model?: string
  temperature?: number
  max_tokens?: number
}

export interface ProjectListResponse {
  projects: ProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
