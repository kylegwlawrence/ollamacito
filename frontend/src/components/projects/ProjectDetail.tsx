import { useEffect, useState } from 'react'
import { useView } from '@/contexts/ViewContext'
import { useProject } from '@/contexts/ProjectContext'
import { useChat } from '@/contexts/ChatContext'
import { useChats } from '@/hooks/useChats'
import { useSettings } from '@/contexts/SettingsContext'
import { useToast } from '@/contexts/ToastContext'
import { projectApi } from '@/services/projectApi'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from '../sidebar/ChatItem'
import { FileUpload } from '../files/FileUpload'
import { FileList } from '../files/FileList'
import type { Chat } from '@/types'
import './ProjectDetail.css'

export const ProjectDetail = () => {
  const { currentProjectId, navigateToProjectSettings, navigateToChat } = useView()
  const { currentProject, setCurrentProject } = useProject()
  const { setCurrentChat } = useChat()
  const { createChat, updateChat, deleteChat } = useChats()
  const { settings } = useSettings()
  const { showToast } = useToast()
  const [projectChats, setProjectChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (currentProjectId) {
      loadProjectData()
    }
  }, [currentProjectId])

  const loadProjectData = async () => {
    if (!currentProjectId) return

    try {
      setLoading(true)
      setError(null)

      // Load project details
      const project = await projectApi.get(currentProjectId)
      setCurrentProject(project)

      // Load project chats
      const chatsResponse = await projectApi.getChats(currentProjectId)
      setProjectChats(chatsResponse.chats)
    } catch (err) {
      console.error('Failed to load project:', err)
      setError('Failed to load project')
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = async () => {
    if (!currentProjectId) return

    try {
      const newChat = await createChat({
        title: 'New Chat',
        model: settings.default_model,
        project_id: currentProjectId,
      })

      if (newChat) {
        setProjectChats((prev) => [newChat, ...prev])
        setCurrentChat(newChat)
        navigateToChat()
      } else {
        showToast('Failed to create chat', 'error')
      }
    } catch (err) {
      console.error('Failed to create chat:', err)
      showToast('Failed to create chat', 'error')
    }
  }

  const handleSelectChat = (chat: Chat) => {
    setCurrentChat(chat)
    navigateToChat()
  }

  const handleRenameChat = async (chatId: string, newTitle: string) => {
    const updatedChat = await updateChat(chatId, { title: newTitle })
    if (updatedChat) {
      setProjectChats((prev) =>
        prev.map((chat) => (chat.id === chatId ? updatedChat : chat))
      )
    }
  }

  const handleChangeModel = async (chatId: string, newModel: string) => {
    const updatedChat = await updateChat(chatId, { model: newModel })
    if (updatedChat) {
      setProjectChats((prev) =>
        prev.map((chat) => (chat.id === chatId ? updatedChat : chat))
      )
    }
  }

  const handleDeleteChat = async (chatId: string) => {
    if (
      window.confirm(
        'Are you sure you want to delete this chat? This action cannot be undone.'
      )
    ) {
      await deleteChat(chatId)
      setProjectChats((prev) => prev.filter((chat) => chat.id !== chatId))
    }
  }

  if (loading) {
    return (
      <div className="project-detail project-detail--loading">
        <LoadingSpinner />
      </div>
    )
  }

  if (error || !currentProject) {
    return (
      <div className="project-detail project-detail--error">
        <h2>Error</h2>
        <p>{error || 'Project not found'}</p>
        <Button onClick={() => navigateToChat()} variant="primary">
          Back to Chats
        </Button>
      </div>
    )
  }

  return (
    <div className="project-detail">
      {/* Header */}
      <div className="project-detail__header">
        <div className="project-detail__title-section">
          <h1 className="project-detail__title">{currentProject.name}</h1>
          <span className="project-detail__chat-count">
            {projectChats.length} {projectChats.length === 1 ? 'chat' : 'chats'}
          </span>
        </div>
        <div className="project-detail__actions">
          <Button
            onClick={() => navigateToProjectSettings(currentProjectId!)}
            variant="secondary"
            size="sm"
          >
            Settings
          </Button>
        </div>
      </div>

      {/* Custom Instructions Preview */}
      {currentProject.custom_instructions && (
        <div className="project-detail__instructions">
          <h3>Custom Instructions</h3>
          <p>{currentProject.custom_instructions}</p>
        </div>
      )}

      {/* Chats Section */}
      <div className="project-detail__section">
        <div className="project-detail__section-header">
          <h2>Chats</h2>
          <Button onClick={handleNewChat} variant="primary" size="sm">
            + New Chat
          </Button>
        </div>

        <div className="project-detail__chats">
          {projectChats.length === 0 ? (
            <div className="project-detail__empty">
              <p>No chats in this project yet.</p>
              <p>Create a new chat to get started!</p>
            </div>
          ) : (
            projectChats.map((chat) => (
              <ChatItem
                key={chat.id}
                chat={chat}
                isActive={false}
                onSelect={handleSelectChat}
                onRename={handleRenameChat}
                onChangeModel={handleChangeModel}
                onDelete={handleDeleteChat}
              />
            ))
          )}
        </div>
      </div>

      {/* Files Section */}
      <div className="project-detail__section">
        <div className="project-detail__section-header">
          <h2>Files</h2>
          <FileUpload projectId={currentProjectId!} onUploadSuccess={loadProjectData} />
        </div>
        <FileList
          projectId={currentProjectId!}
          files={currentProject.files || []}
          onFileDeleted={loadProjectData}
        />
      </div>

      {/* Memory Section - Placeholder for future */}
      <div className="project-detail__section">
        <div className="project-detail__section-header">
          <h2>Memory</h2>
          <button className="project-detail__button-disabled" disabled>
            Generate Memory
          </button>
        </div>
        <div className="project-detail__placeholder">
          <p>Memory generation coming soon</p>
        </div>
      </div>
    </div>
  )
}
