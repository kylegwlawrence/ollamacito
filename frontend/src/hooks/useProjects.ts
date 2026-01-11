import { useState, useCallback, useEffect } from 'react'
import { projectApi } from '@/services/projectApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { ProjectResponse, ProjectCreate, ProjectUpdate } from '@/types'

export const useProjects = () => {
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

  return {
    projects,
    loading,
    error,
    loadProjects,
    createProject,
    updateProject,
    deleteProject,
  }
}
