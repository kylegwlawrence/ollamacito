import { useEffect, useState } from 'react'
import { useMatch, useNavigate } from 'react-router-dom'
import { useChatStore } from '@/stores/chatStore'
import { useChats } from '@/hooks/useChats'
import { useSettingsStore } from '@/stores/settingsStore'
import { useConfirmStore } from '@/stores/confirmStore'
import { useProjectsStore } from '@/stores/projectsStore'
import { usePromptStore } from '@/stores/promptStore'
import { useToastStore } from '@/stores/toastStore'
import { Button } from '../common/Button'
import { Icon } from '../common/Icon'
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
  const projects = useProjectsStore((s) => s.projects)
  const projectsLoading = useProjectsStore((s) => s.loading)
  const createProject = useProjectsStore((s) => s.createProject)
  const deleteProject = useProjectsStore((s) => s.deleteProject)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)
  const prompt = usePromptStore((s) => s.ask)

  const navigate = useNavigate()
  const projectMatch = useMatch('/projects/:projectId/*')
  const currentProjectId = projectMatch?.params.projectId ?? null

  const [projectsExpanded, setProjectsExpanded] = useState(true)
  const [chatsExpanded, setChatsExpanded] = useState(true)

  useEffect(() => {
    loadChats()
  }, [loadChats])

  const handleNewChat = async () => {
    const newChat = await createChat({
      title: 'New Chat',
      model: settings.default_model,
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
    const name = await prompt({
      title: 'Create new project',
      placeholder: 'Project name',
      confirmLabel: 'Create',
    })
    if (!name) return

    try {
      const newProject = await createProject(name)
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
      {/* Brand */}
      <div className="sidebar__brand">
        <img src="/green_logo_3.png" alt="Logo" className="sidebar__logo" />
        <h1 className="sidebar__title">Ollama::cito</h1>
      </div>

      {/* Actions */}
      <div className="sidebar__actions">
        <Button
          onClick={handleNewChat}
          variant="primary"
          size="sm"
          leadingIcon="edit_square"
          title="Create a new chat"
          aria-label="Create a new chat"
        >
          New Chat
        </Button>
        <Button
          onClick={handleCreateProject}
          variant="secondary"
          size="sm"
          leadingIcon="create_new_folder"
          title="Create a new project"
          aria-label="Create a new project"
        >
          New Project
        </Button>
      </div>

      {/* Scrollable sections */}
      <div className="sidebar__scrollable">
        {/* Projects */}
        <section className="sidebar__group" aria-labelledby="projects-heading">
          <button
            className="sidebar__group-header"
            onClick={() => setProjectsExpanded(!projectsExpanded)}
            aria-expanded={projectsExpanded}
            aria-controls="projects-list"
          >
            <span id="projects-heading" className="sidebar__group-label">Projects</span>
            <Icon
              name="expand_more"
              size={16}
              className={`sidebar__group-chevron${projectsExpanded ? ' sidebar__group-chevron--open' : ''}`}
            />
          </button>

          {projectsExpanded && (
            <div id="projects-list" className="sidebar__group-items" role="list">
              {projectsLoading ? (
                <div className="sidebar__loading">
                  <LoadingSpinner />
                </div>
              ) : projects.length === 0 ? (
                <div className="sidebar__empty">
                  <p>No projects yet</p>
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

        {/* Chats */}
        <section className="sidebar__group" aria-labelledby="chats-heading">
          <button
            className="sidebar__group-header"
            onClick={() => setChatsExpanded(!chatsExpanded)}
            aria-expanded={chatsExpanded}
            aria-controls="chats-list"
          >
            <span id="chats-heading" className="sidebar__group-label">Chats</span>
            <Icon
              name="expand_more"
              size={16}
              className={`sidebar__group-chevron${chatsExpanded ? ' sidebar__group-chevron--open' : ''}`}
            />
          </button>

          {chatsExpanded && (
            <div id="chats-list" className="sidebar__group-items" role="list">
              {loading && (
                <div className="sidebar__loading">
                  <LoadingSpinner />
                </div>
              )}
              {!loading && standaloneChats.length === 0 && (
                <div className="sidebar__empty">
                  <p>No standalone chats</p>
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
      </div>

      {/* Footer: RAG servers + settings */}
      <div className="sidebar__footer">
        <button
          className="sidebar__settings-link"
          onClick={() => navigate('/rag-servers')}
          title="Manage RAG servers"
          aria-label="Manage RAG servers"
        >
          <Icon name="database" size={18} />
          <span>RAG Servers</span>
        </button>
        <button
          className="sidebar__settings-link"
          onClick={() => navigate('/settings')}
          title="Application settings"
          aria-label="Open application settings"
        >
          <Icon name="settings" size={18} />
          <span>Settings</span>
        </button>
      </div>
    </nav>
  )
}
