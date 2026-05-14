/**
 * Projects store (PLAN_NEW.md Phase 5).
 *
 * Replaces ProjectContext. Holds:
 * - `projects`: the list of project summaries shown in the sidebar
 * - `currentProject`: the full project (with files + chats) for the page
 *   currently looking at one specific project
 *
 * Auto-load with `useProjectsAutoLoad()` from a top-level component.
 */
import { create } from 'zustand'
import { useEffect } from 'react'
import { projectApi } from '@/services/projectApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { ProjectResponse, ProjectUpdate, ProjectWithDetails } from '@/types'

interface ProjectsStore {
  projects: ProjectResponse[]
  loading: boolean
  loaded: boolean
  error: string | null

  currentProject: ProjectWithDetails | null
  setCurrentProject: (project: ProjectWithDetails | null) => void

  loadProjects: () => Promise<void>
  createProject: (
    name: string,
    instructions?: string
  ) => Promise<ProjectResponse | null>
  updateProject: (
    id: string,
    updates: ProjectUpdate
  ) => Promise<ProjectResponse | null>
  deleteProject: (id: string) => Promise<void>
  adjustChatCount: (id: string, delta: number) => void
}

export const useProjectsStore = create<ProjectsStore>((set, get) => ({
  projects: [],
  loading: true,
  loaded: false,
  error: null,
  currentProject: null,

  setCurrentProject: (project) => set({ currentProject: project }),

  loadProjects: async () => {
    try {
      set({ loading: true, error: null })
      const response = await projectApi.list(1, 100, false)
      set({ projects: response.projects, loaded: true })
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to load projects') })
    } finally {
      set({ loading: false })
    }
  },

  createProject: async (name, instructions) => {
    try {
      const newProject = await projectApi.create({
        name,
        custom_instructions: instructions,
      })
      set((s) => ({ projects: [newProject, ...s.projects] }))
      return newProject
    } catch (err) {
      console.error('Error creating project:', err)
      set({ error: getErrorMessage(err, 'Failed to create project') })
      return null
    }
  },

  updateProject: async (id, updates) => {
    try {
      const updated = await projectApi.update(id, updates)
      set((s) => ({
        projects: s.projects.map((p) => (p.id === id ? updated : p)),
      }))
      return updated
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to update project') })
      return null
    }
  },

  adjustChatCount: (id, delta) => {
    set((s) => ({
      projects: s.projects.map((p) =>
        p.id === id ? { ...p, chat_count: Math.max(0, p.chat_count + delta) } : p
      ),
      currentProject:
        s.currentProject?.id === id
          ? { ...s.currentProject, chat_count: Math.max(0, s.currentProject.chat_count + delta) }
          : s.currentProject,
    }))
  },

  deleteProject: async (id) => {
    try {
      await projectApi.delete(id)
      set((s) => ({
        projects: s.projects.filter((p) => p.id !== id),
        currentProject:
          s.currentProject?.id === id ? null : s.currentProject,
      }))
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to delete project') })
      throw err
    }
  },
}))

/** Mount once near the top to fetch projects on first paint. */
export const useProjectsAutoLoad = (): void => {
  const loaded = useProjectsStore((s) => s.loaded)
  const loadProjects = useProjectsStore((s) => s.loadProjects)
  useEffect(() => {
    if (!loaded) {
      loadProjects()
    }
  }, [loaded, loadProjects])
}
