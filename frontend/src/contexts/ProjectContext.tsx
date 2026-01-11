import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import type { ProjectWithDetails, ProjectResponse, ProjectUpdate } from '@/types'
import { projectApi } from '@/services/projectApi'
import { getErrorMessage } from '@/utils/errorHandler'

interface ProjectContextType {
  // Current project detail
  currentProject: ProjectWithDetails | null
  setCurrentProject: (project: ProjectWithDetails | null) => void

  // Projects list
  projects: ProjectResponse[]
  loading: boolean
  error: string | null

  // CRUD operations
  loadProjects: () => Promise<void>
  createProject: (name: string, instructions?: string) => Promise<ProjectResponse | null>
  updateProject: (id: string, updates: ProjectUpdate) => Promise<ProjectResponse | null>
  deleteProject: (id: string) => Promise<void>
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const [currentProject, setCurrentProject] = useState<ProjectWithDetails | null>(null)
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await projectApi.list(1, 100, false)
      setProjects(response.projects)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load projects'))
    } finally {
      setLoading(false)
    }
  }, [])

  const createProject = useCallback(
    async (name: string, instructions?: string): Promise<ProjectResponse | null> => {
      try {
        const newProject = await projectApi.create({
          name,
          custom_instructions: instructions,
        })
        setProjects((prev) => [newProject, ...prev])
        return newProject
      } catch (err) {
        console.error('Error creating project:', err)
        setError(getErrorMessage(err, 'Failed to create project'))
        return null
      }
    },
    []
  )

  const updateProject = useCallback(
    async (id: string, updates: ProjectUpdate): Promise<ProjectResponse | null> => {
      try {
        const updated = await projectApi.update(id, updates)
        setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)))
        return updated
      } catch (err) {
        setError(getErrorMessage(err, 'Failed to update project'))
        return null
      }
    },
    []
  )

  const deleteProject = useCallback(async (id: string) => {
    try {
      await projectApi.delete(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete project'))
      throw err
    }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  return (
    <ProjectContext.Provider
      value={{
        currentProject,
        setCurrentProject,
        projects,
        loading,
        error,
        loadProjects,
        createProject,
        updateProject,
        deleteProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  )
}

export const useProject = () => {
  const context = useContext(ProjectContext)
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider')
  }
  return context
}
