import { useEffect, useState } from 'react'
import { useChat } from '@/contexts/ChatContext'
import { useChats } from '@/hooks/useChats'
import { useSettings } from '@/contexts/SettingsContext'
import { useModels } from '@/hooks/useModels'
import { useProject } from '@/contexts/ProjectContext'
import { useView } from '@/contexts/ViewContext'
import { useToast } from '@/contexts/ToastContext'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from './ChatItem'
import { ProjectItem } from './ProjectItem'
import type { Chat } from '@/types'
import './Sidebar.css'

export const Sidebar = () => {
  const { currentChat, setCurrentChat } = useChat()
  const { chats, loading, loadChats, createChat, updateChat, deleteChat } = useChats()
  const { settings } = useSettings()
  const { models } = useModels()
  const { projects, loading: projectsLoading, createProject, deleteProject } = useProject()
  const { viewType, currentProjectId, navigateToChat, navigateToProject, navigateToAppSettings } = useView()
  const { showToast } = useToast()
  const [selectedModel, setSelectedModel] = useState<string>(settings.default_model)
  const [projectsExpanded, setProjectsExpanded] = useState(true)
  const [chatsExpanded, setChatsExpanded] = useState(true)

  useEffect(() => {
    loadChats()
  }, [loadChats])

  useEffect(() => {
    setSelectedModel(settings.default_model)
  }, [settings.default_model])

  const handleNewChat = async () => {
    const newChat = await createChat({
      title: 'New Chat',
      model: selectedModel,
    })
    if (newChat) {
      setCurrentChat(newChat)
    }
  }

  const handleRename = async (chatId: string, newTitle: string) => {
    const updatedChat = await updateChat(chatId, { title: newTitle })
    if (updatedChat && currentChat?.id === chatId) {
      setCurrentChat(updatedChat)
    }
  }

  const handleChangeModel = async (chatId: string, newModel: string) => {
    const updatedChat = await updateChat(chatId, { model: newModel })
    if (updatedChat && currentChat?.id === chatId) {
      setCurrentChat(updatedChat)
    }
  }

  const handleDelete = async (chatId: string) => {
    if (window.confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
      await deleteChat(chatId)
      if (currentChat?.id === chatId) {
        setCurrentChat(null)
      }
    }
  }

  const handleSelectChat = (chat: Chat) => {
    setCurrentChat(chat)
    navigateToChat()
  }

  const handleCreateProject = async () => {
    const name = window.prompt('Enter project name:')
    if (!name?.trim()) return

    try {
      const newProject = await createProject(name.trim())
      if (newProject) {
        showToast('Project created successfully', 'success')
        navigateToProject(newProject.id)
      } else {
        showToast('Failed to create project', 'error')
      }
    } catch (err) {
      console.error('Failed to create project:', err)
      showToast('Failed to create project', 'error')
    }
  }

  const handleDeleteProject = async (projectId: string, chatCount: number) => {
    const msg = chatCount > 0
      ? `Delete this project and its ${chatCount} chat(s)? This action cannot be undone.`
      : 'Delete this project? This action cannot be undone.'

    if (!window.confirm(msg)) return

    try {
      await deleteProject(projectId)
      showToast('Project deleted successfully', 'success')
      if (currentProjectId === projectId) {
        // Clear chat state to show clean landing page
        setCurrentChat(null)
        navigateToChat()
      }
    } catch (err) {
      console.error('Failed to delete project:', err)
      showToast('Failed to delete project', 'error')
    }
  }

  // Filter standalone chats (not in any project)
  const standaloneChats = chats.filter(chat => !chat.project_id)

  return (
    <nav className="sidebar" aria-label="Main navigation">
      <div className="sidebar__header">
        <h1 className="sidebar__title">Ollama::cito</h1>
        <img src="/green_logo_filled.png" alt="Logo" className="sidebar__logo"/>
        <Button
          onClick={handleCreateProject}
          variant="primary"
          size="sm"
          title="Create a new project"
          aria-label="Create a new project"
        >
          + Create Project
        </Button>
        <Button
          onClick={handleNewChat}
          variant="primary"
          size="sm"
          title="Create a new chat"
          aria-label="Create a new chat"
        >
          + New Chat
        </Button>
        <div className="sidebar__model-selector">
          <label htmlFor="model-select" className="sidebar__model-label">
            Model:
          </label>
          <select
            id="model-select"
            className="sidebar__model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            title="Select a model for new chats"
          >
            {models.map((model) => (
              <option key={model.name} value={model.name}>
                {model.name}
              </option>
            ))}
          </select>
        </div>
        <Button
          onClick={navigateToAppSettings}
          variant="secondary"
          size="sm"
          title="Application settings"
          aria-label="Open application settings"
        >
          ⚙️ Settings
        </Button>
      </div>

      {/* Projects Section */}
      <section className="sidebar__section" aria-labelledby="projects-heading">
        <button
          className="sidebar__section-header"
          onClick={() => setProjectsExpanded(!projectsExpanded)}
          aria-expanded={projectsExpanded}
          aria-controls="projects-list"
        >
          <span id="projects-heading">{projectsExpanded ? '▼' : '▶'} Projects</span>
        </button>

        {projectsExpanded && (
          <div id="projects-list" className="sidebar__projects" role="list">
            {projectsLoading ? (
              <div className="sidebar__loading">
                <LoadingSpinner />
              </div>
            ) : projects.length === 0 ? (
              <div className="sidebar__empty">
                <p>No projects yet. Create one to organize your chats!</p>
              </div>
            ) : (
              projects.map((project) => (
                <ProjectItem
                  key={project.id}
                  project={project}
                  isActive={viewType === 'project-detail' && currentProjectId === project.id}
                  onSelect={() => navigateToProject(project.id)}
                  onDelete={() => handleDeleteProject(project.id, project.chat_count)}
                />
              ))
            )}
          </div>
        )}
      </section>

      {/* Chats Section - Only standalone chats */}
      <section className="sidebar__section" aria-labelledby="chats-heading">
        <button
          className="sidebar__section-header"
          onClick={() => setChatsExpanded(!chatsExpanded)}
          aria-expanded={chatsExpanded}
          aria-controls="chats-list"
        >
          <span id="chats-heading">{chatsExpanded ? '▼' : '▶'} Chats</span>
        </button>

        {chatsExpanded && (
          <div id="chats-list" className="sidebar__chats" role="list">
            {loading && (
              <div className="sidebar__loading">
                <LoadingSpinner />
              </div>
            )}

            {!loading && standaloneChats.length === 0 && (
              <div className="sidebar__empty">
                <p>No standalone chats yet.</p>
              </div>
            )}

            {standaloneChats.map((chat) => (
              <ChatItem
                key={chat.id}
                chat={chat}
                isActive={currentChat?.id === chat.id}
                onSelect={handleSelectChat}
                onRename={handleRename}
                onChangeModel={handleChangeModel}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </section>
    </nav>
  )
}
