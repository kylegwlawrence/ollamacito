/**
 * Project-related TypeScript types.
 */

export interface Project {
  id: string
  name: string
  custom_instructions: string | null
  is_archived: boolean
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
  created_at: string
  updated_at: string
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
}

export interface ProjectUpdate {
  name?: string
  custom_instructions?: string
  is_archived?: boolean
}

export interface ProjectListResponse {
  projects: ProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
