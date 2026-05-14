import { useEffect, useState } from 'react'
import { useMatch, useNavigate } from 'react-router-dom'
import { useChatStore } from '@/stores/chatStore'
import { useChats } from '@/hooks/useChats'
import { useSettingsStore } from '@/stores/settingsStore'
import { useModels } from '@/hooks/useModels'
import { useConfirmStore } from '@/stores/confirmStore'
import { useProjectsStore } from '@/stores/projectsStore'
import { useToastStore } from '@/stores/toastStore'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from './ChatItem'
import { ProjectItem } from './ProjectItem'
import type { Chat } from '@/types'
import './Sidebar.css'

export const Sidebar = () => {
  const currentChat = useChatStore((s) => s.currentChat)
  const setCurrentChat = useChatStore((s) => s.setCurrentChat)
  const { chats, loading, loadChats, createChat, updateChat, deleteChat } = useChats()
  const settings = useSettingsStore((s) => s.settings)
  const { models } = useModels()
  const projects = useProjectsStore((s) => s.projects)
  const projectsLoading = useProjectsStore((s) => s.loading)
  const createProject = useProjectsStore((s) => s.createProject)
  const deleteProject = useProjectsStore((s) => s.deleteProject)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)

  // URL-derived state — used for highlighting the active project + deciding
  // where "go back to chat" navigates after a destructive action.
  const navigate = useNavigate()
  const projectMatch = useMatch('/projects/:projectId/*')
  const currentProjectId = projectMatch?.params.projectId ?? null

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
      navigate(`/chats/${newChat.id}`)
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
    const ok = await confirm({
      title: 'Delete this chat?',
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    await deleteChat(chatId)
    if (currentChat?.id === chatId) {
      setCurrentChat(null)
      navigate('/')
    }
  }

  const handleSelectChat = (chat: Chat) => {
    setCurrentChat(chat)
    navigate(`/chats/${chat.id}`)
  }

  const handleCreateProject = async () => {
    const name = window.prompt('Enter project name:')
    if (!name?.trim()) return

    try {
      const newProject = await createProject(name.trim())
      if (newProject) {
        showToast('Project created successfully', 'success')
        navigate(`/projects/${newProject.id}`)
      } else {
        showToast('Failed to create project', 'error')
      }
    } catch (err) {
      console.error('Failed to create project:', err)
      showToast('Failed to create project', 'error')
    }
  }

  const handleDeleteProject = async (projectId: string, chatCount: number) => {
    const ok = await confirm({
      title: chatCount > 0 ? `Delete this project and its ${chatCount} chat(s)?` : 'Delete this project?',
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return

    try {
      await deleteProject(projectId)
      showToast('Project deleted successfully', 'success')
      if (currentProjectId === projectId) {
        setCurrentChat(null)
        navigate('/')
      }
    } catch (err) {
      console.error('Failed to delete project:', err)
      showToast('Failed to delete project', 'error')
    }
  }

  const standaloneChats = chats.filter((chat) => !chat.project_id)

  return (
    <nav className="sidebar" aria-label="Main navigation">
      <div className="sidebar__header">
        <h1 className="sidebar__title">Ollama::cito</h1>
        <img src="/green_logo_3.png" alt="Logo" className="sidebar__logo" />
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
          onClick={() => navigate('/settings')}
          variant="secondary"
          size="sm"
          title="Application settings"
          aria-label="Open application settings"
        >
          Settings
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
                  isActive={currentProjectId === project.id}
                  onSelect={() => navigate(`/projects/${project.id}`)}
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
