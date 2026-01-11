import { createContext, useContext, useState, ReactNode } from 'react'
import type { ProjectWithDetails } from '@/types'

interface ProjectContextType {
  currentProject: ProjectWithDetails | null
  setCurrentProject: (project: ProjectWithDetails | null) => void
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const [currentProject, setCurrentProject] = useState<ProjectWithDetails | null>(null)

  return (
    <ProjectContext.Provider value={{ currentProject, setCurrentProject }}>
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
