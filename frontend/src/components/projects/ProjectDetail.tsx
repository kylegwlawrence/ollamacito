import { useEffect, useState } from 'react'
import { useView } from '@/contexts/ViewContext'
import { useProject } from '@/contexts/ProjectContext'
import { useChat } from '@/contexts/ChatContext'
import { useChats } from '@/hooks/useChats'
import { useSettings } from '@/contexts/SettingsContext'
import { useModels } from '@/hooks/useModels'
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
  const { currentProjectId, navigateToChat } = useView()
  const { currentProject, setCurrentProject, updateProject } = useProject()
  const { setCurrentChat } = useChat()
  const { createChat, updateChat, deleteChat } = useChats()
  const { settings } = useSettings()
  const { models } = useModels()
  const { showToast } = useToast()
  const [projectChats, setProjectChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>(
    currentProject?.default_model || settings.default_model
  )

  // Settings form state
  const [settingsExpanded, setSettingsExpanded] = useState(false)
  const [editedName, setEditedName] = useState('')
  const [editedInstructions, setEditedInstructions] = useState('')
  const [editedDefaultModel, setEditedDefaultModel] = useState('')
  const [editedTemperature, setEditedTemperature] = useState('')
  const [editedMaxTokens, setEditedMaxTokens] = useState('')
  const [hasSettingsChanges, setHasSettingsChanges] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)

  useEffect(() => {
    if (currentProjectId) {
      loadProjectData()
    }
  }, [currentProjectId])

  useEffect(() => {
    const modelToUse = currentProject?.default_model || settings.default_model
    setSelectedModel(modelToUse)
  }, [currentProject?.default_model, settings.default_model, currentProject])

  // Initialize settings form when project loads
  useEffect(() => {
    if (currentProject) {
      setEditedName(currentProject.name)
      setEditedInstructions(currentProject.custom_instructions || '')
      setEditedDefaultModel(currentProject.default_model || '')
      setEditedTemperature(currentProject.temperature?.toString() || '')
      setEditedMaxTokens(currentProject.max_tokens?.toString() || '')
    }
  }, [currentProject])

  // Track settings changes
  useEffect(() => {
    if (currentProject) {
      const nameChanged = editedName !== currentProject.name
      const instructionsChanged = editedInstructions !== (currentProject.custom_instructions || '')
      const modelChanged = editedDefaultModel !== (currentProject.default_model || '')
      const tempChanged = editedTemperature !== (currentProject.temperature?.toString() || '')
      const tokensChanged = editedMaxTokens !== (currentProject.max_tokens?.toString() || '')
      setHasSettingsChanges(nameChanged || instructionsChanged || modelChanged || tempChanged || tokensChanged)
    }
  }, [editedName, editedInstructions, editedDefaultModel, editedTemperature, editedMaxTokens, currentProject])

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
        model: selectedModel,
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

  const handleSaveSettings = async () => {
    if (!currentProjectId || !currentProject) return

    if (!editedName.trim()) {
      showToast('Project name cannot be empty', 'warning')
      return
    }

    try {
      setSavingSettings(true)

      const updated = await updateProject(currentProjectId, {
        name: editedName.trim(),
        custom_instructions: editedInstructions.trim() || undefined,
        default_model: editedDefaultModel.trim() || undefined,
        temperature: editedTemperature ? parseFloat(editedTemperature) : undefined,
        max_tokens: editedMaxTokens ? parseInt(editedMaxTokens, 10) : undefined,
      })

      if (updated) {
        setCurrentProject({
          ...updated,
          files: currentProject.files,
        })
        setHasSettingsChanges(false)
        showToast('Project settings saved successfully!', 'success')
      }
    } catch (err) {
      console.error('Failed to save project:', err)
      showToast('Failed to save project settings', 'error')
    } finally {
      setSavingSettings(false)
    }
  }

  const handleCancelSettings = () => {
    if (currentProject) {
      setEditedName(currentProject.name)
      setEditedInstructions(currentProject.custom_instructions || '')
      setEditedDefaultModel(currentProject.default_model || '')
      setEditedTemperature(currentProject.temperature?.toString() || '')
      setEditedMaxTokens(currentProject.max_tokens?.toString() || '')
      setHasSettingsChanges(false)
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
      </div>

      {/* Project Settings Section */}
      <div className="project-detail__section">
        <div
          className="project-detail__section-header project-detail__section-header--clickable"
          onClick={() => setSettingsExpanded(!settingsExpanded)}
          style={{ cursor: 'pointer' }}
        >
          <h2>
            {settingsExpanded ? '▼' : '▶'} Project Settings
          </h2>
        </div>

        {settingsExpanded && (
          <div className="project-detail__settings-form">
            {/* Project Name */}
            <div className="project-detail__field">
              <label htmlFor="project-name-edit" className="project-detail__label">
                Project Name <span className="project-detail__required">*</span>
              </label>
              <input
                id="project-name-edit"
                type="text"
                className="project-detail__input"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
                placeholder="Enter project name"
                maxLength={255}
              />
            </div>

            {/* Custom Instructions */}
            <div className="project-detail__field">
              <label htmlFor="custom-instructions-edit" className="project-detail__label">
                Custom Instructions
              </label>
              <textarea
                id="custom-instructions-edit"
                className="project-detail__textarea"
                value={editedInstructions}
                onChange={(e) => setEditedInstructions(e.target.value)}
                placeholder="Enter custom instructions for this project (optional)"
                rows={6}
              />
              <span className="project-detail__hint">
                These instructions will be sent with every message in project chats
              </span>
            </div>

            {/* Model Settings */}
            <div className="project-detail__model-settings">
              <h3 className="project-detail__subsection-title">Model Settings</h3>
              <p className="project-detail__subsection-description">
                Override global defaults for this project. Leave blank to use global settings.
              </p>

              <div className="project-detail__model-fields">
                {/* Default Model */}
                <div className="project-detail__field">
                  <label htmlFor="default-model-edit" className="project-detail__label">
                    Default Model
                  </label>
                  <select
                    id="default-model-edit"
                    className="project-detail__select"
                    value={editedDefaultModel}
                    onChange={(e) => setEditedDefaultModel(e.target.value)}
                  >
                    <option value="">Use Global Default ({settings.default_model})</option>
                    {models.map((model) => (
                      <option key={model.name} value={model.name}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Temperature */}
                <div className="project-detail__field">
                  <label htmlFor="temperature-edit" className="project-detail__label">
                    Temperature
                  </label>
                  <input
                    id="temperature-edit"
                    type="number"
                    className="project-detail__input"
                    value={editedTemperature}
                    onChange={(e) => setEditedTemperature(e.target.value)}
                    placeholder={`Global default: ${settings.default_temperature}`}
                    min="0"
                    max="2"
                    step="0.1"
                  />
                  <span className="project-detail__hint">
                    Controls randomness (0.0-2.0)
                  </span>
                </div>

                {/* Max Tokens */}
                <div className="project-detail__field">
                  <label htmlFor="max-tokens-edit" className="project-detail__label">
                    Max Tokens
                  </label>
                  <input
                    id="max-tokens-edit"
                    type="number"
                    className="project-detail__input"
                    value={editedMaxTokens}
                    onChange={(e) => setEditedMaxTokens(e.target.value)}
                    placeholder={`Global default: ${settings.default_max_tokens}`}
                    min="1"
                    step="1"
                  />
                  <span className="project-detail__hint">
                    Maximum context window size
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            {hasSettingsChanges && (
              <div className="project-detail__settings-actions">
                <Button
                  onClick={handleSaveSettings}
                  variant="primary"
                  size="sm"
                  disabled={savingSettings}
                >
                  {savingSettings ? 'Saving...' : 'Save Changes'}
                </Button>
                <Button
                  onClick={handleCancelSettings}
                  variant="secondary"
                  size="sm"
                  disabled={savingSettings}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Custom Instructions Preview */}
      {!settingsExpanded && currentProject.custom_instructions && (
        <div className="project-detail__instructions">
          <h3>Custom Instructions</h3>
          <p>{currentProject.custom_instructions}</p>
        </div>
      )}

      {/* Chats Section */}
      <div className="project-detail__section">
        <div className="project-detail__section-header">
          <h2>Chats</h2>
          <div className="project-detail__chat-actions">
            <div className="project-detail__model-selector">
              <label htmlFor="project-model-select" className="project-detail__model-label">
                Model:
              </label>
              <select
                id="project-model-select"
                className="project-detail__model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                title="Select a model for new chats"
              >
                {models.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.name}
                    {currentProject.default_model === model.name ? ' (Project Default)' : ''}
                    {!currentProject.default_model && settings.default_model === model.name ? ' (Global Default)' : ''}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={handleNewChat} variant="primary" size="sm">
              + New Chat
            </Button>
          </div>
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
