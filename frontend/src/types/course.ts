/**
 * Course-generator TypeScript types.
 *
 * These are hand-mirrored from the Pydantic schemas in
 * backend/app/schemas/course.py. Keep this file in lockstep with the backend.
 */

export type ExpertiseLevel =
  | 'none'
  | 'novice'
  | 'competent'
  | 'proficient'
  | 'expert'

export const EXPERTISE_LEVELS: ExpertiseLevel[] = [
  'none',
  'novice',
  'competent',
  'proficient',
  'expert',
]

export type AgeCategory =
  | 'primary'
  | 'elementary'
  | 'junior_high'
  | 'senior_high'
  | 'college'
  | 'bachelors'
  | 'masters'
  | 'phd'

export const AGE_CATEGORY_LABELS: Record<AgeCategory, string> = {
  primary: 'Primary school (grade 1-3)',
  elementary: 'Elementary school (grade 4-7)',
  junior_high: 'Junior high (grade 8-9)',
  senior_high: 'Senior high (grade 10-12)',
  college: 'College (non-US) / community college',
  bachelors: "University bachelor's",
  masters: "University master's",
  phd: 'University PhD',
}

export type ResourceType =
  | 'readings'
  | 'practice_questions'
  | 'quizzes'
  | 'projects'

export const RESOURCE_LABELS: Record<ResourceType, string> = {
  readings: 'Readings',
  practice_questions: 'Practice questions',
  quizzes: 'Quizzes',
  projects: 'Projects',
}

export type BloomLevel =
  | 'remember'
  | 'understand'
  | 'apply'
  | 'analyze'
  | 'evaluate'
  | 'create'

export type AssessmentType =
  | 'quiz'
  | 'practice_question'
  | 'project'
  | 'reflection'

export type CourseStatus =
  | 'pending'
  | 'generating'
  | 'complete'
  | 'needs_review'
  | 'failed'

// ---- Input -----------------------------------------------------------------

export interface CourseGenerationRequest {
  topic: string
  current_expertise: ExpertiseLevel
  target_expertise: ExpertiseLevel
  age_category: AgeCategory
  hours_min: number
  hours_max: number
  included_resources: ResourceType[]
  learner_context?: string | null
}

// ---- Output ----------------------------------------------------------------

export interface Outcome {
  id: string
  text: string
  bloom_level: BloomLevel
}

export interface Objective {
  id: string
  text: string
  bloom_level: BloomLevel
}

export interface Reading {
  title: string
  url: string
  snippet?: string | null
}

export interface Assessment {
  id: string
  type: AssessmentType
  prompt: string
  assesses_outcome_ids: string[]
}

export interface Lesson {
  id: string
  title: string
  summary: string
  estimated_hours: number
  objectives: Objective[]
  prerequisite_ids: string[]
  readings: Reading[]
  assessments: Assessment[]
}

export interface Module {
  id: string
  title: string
  summary: string
  estimated_hours: number
  outcomes: Outcome[]
  lessons: Lesson[]
}

export interface CourseOutline {
  title: string
  summary: string
  target_audience: string
  total_hours: number
  course_outcomes: Outcome[]
  modules: Module[]
}

// ---- API rows --------------------------------------------------------------

export interface ValidationErrorEntry {
  path: string
  msg: string
}

export interface Course {
  id: string
  user_id: string
  rag_server_id: string
  rag_top_k: number
  title: string
  status: CourseStatus
  input: CourseGenerationRequest
  outline: CourseOutline | null
  validation_errors: ValidationErrorEntry[] | null
  override_model: string | null
  override_temperature: number | null
  override_num_ctx: number | null
  model_used: string | null
  created_at: string
  updated_at: string
  generated_at: string | null
}

export interface CourseListItem {
  id: string
  title: string
  rag_server_id: string
  rag_top_k: number
  status: CourseStatus
  total_hours: number | null
  topic: string
  created_at: string
  updated_at: string
  generated_at: string | null
}

export interface CourseCreate {
  rag_server_id: string
  rag_top_k: number
  input: CourseGenerationRequest
  override_model?: string | null
  override_temperature?: number | null
  override_num_ctx?: number | null
}

export interface CourseUpdate {
  title?: string
  rag_server_id?: string
  rag_top_k?: number
  override_model?: string | null
  override_temperature?: number | null
  override_num_ctx?: number | null
}

export interface CourseRegenerateRequest {
  input?: CourseGenerationRequest
}

// ---- Streaming frames ------------------------------------------------------

export type PhaseFrame = {
  type: 'phase'
  name: 'research' | 'assembling'
}
export type ChunkFrame = { type: 'chunk'; content: string }
export type ToolCallFrame = {
  type: 'tool_call'
  id: string
  name: string
  input: Record<string, unknown>
}
export type ToolResultFrame = {
  type: 'tool_result'
  id: string
  ok: boolean
  summary?: string
  error?: string
}
export type OutlineFrame = { type: 'outline'; content: CourseOutline }
export type ValidationFrame = {
  type: 'validation'
  errors: ValidationErrorEntry[]
}
export type DoneFrame = {
  type: 'done'
  status: 'complete' | 'needs_review' | 'failed'
}
export type ErrorFrame = { type: 'error'; message: string }

export type GenerationFrame =
  | PhaseFrame
  | ChunkFrame
  | ToolCallFrame
  | ToolResultFrame
  | OutlineFrame
  | ValidationFrame
  | DoneFrame
  | ErrorFrame
