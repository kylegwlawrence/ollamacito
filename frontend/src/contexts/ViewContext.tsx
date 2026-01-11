import { createContext, useContext, useState, ReactNode } from 'react'

type ViewType = 'chat' | 'project-detail' | 'project-settings'

interface ViewContextType {
  viewType: ViewType
  currentProjectId: string | null
  navigateToChat: () => void
  navigateToProject: (projectId: string) => void
  navigateToProjectSettings: (projectId: string) => void
}

const ViewContext = createContext<ViewContextType | undefined>(undefined)

export const ViewProvider = ({ children }: { children: ReactNode }) => {
  const [viewType, setViewType] = useState<ViewType>('chat')
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null)

  const navigateToChat = () => {
    setViewType('chat')
    setCurrentProjectId(null)
  }

  const navigateToProject = (projectId: string) => {
    setViewType('project-detail')
    setCurrentProjectId(projectId)
  }

  const navigateToProjectSettings = (projectId: string) => {
    setViewType('project-settings')
    setCurrentProjectId(projectId)
  }

  return (
    <ViewContext.Provider
      value={{
        viewType,
        currentProjectId,
        navigateToChat,
        navigateToProject,
        navigateToProjectSettings,
      }}
    >
      {children}
    </ViewContext.Provider>
  )
}

export const useView = () => {
  const context = useContext(ViewContext)
  if (context === undefined) {
    throw new Error('useView must be used within a ViewProvider')
  }
  return context
}
