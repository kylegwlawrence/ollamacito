import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectsStore } from '@/stores/projectsStore'
import { useChatStore } from '@/stores/chatStore'
import { useChats } from '@/hooks/useChats'
import { useSettingsStore } from '@/stores/settingsStore'
import { useModels } from '@/hooks/useModels'
import { useToastStore } from '@/stores/toastStore'
import { useConfirmStore } from '@/stores/confirmStore'
import { projectApi } from '@/services/projectApi'
import { ragApi } from '@/services/ragApi'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from '../sidebar/ChatItem'
import { FileUpload } from '../files/FileUpload'
import { FileList } from '../files/FileList'
import type { Chat, RagInfo } from '@/types'
import './ProjectDetail.css'

export const ProjectDetail = () => {
  const { projectId: currentProjectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const currentProject = useProjectsStore((s) => s.currentProject)
  const setCurrentProject = useProjectsStore((s) => s.setCurrentProject)
  const updateProject = useProjectsStore((s) => s.updateProject)
  const adjustChatCount = useProjectsStore((s) => s.adjustChatCount)
  const setCurrentChat = useChatStore((s) => s.setCurrentChat)
  const { createChat, updateChat, deleteChat } = useChats()
  const settings = useSettingsStore((s) => s.settings)
  const { models } = useModels()
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)
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
  const [editedAutoAttachAllFiles, setEditedAutoAttachAllFiles] = useState(false)
  const [editedRagEnabled, setEditedRagEnabled] = useState(false)
  const [editedRagServerUrl, setEditedRagServerUrl] = useState('')
  const [editedRagCorpusId, setEditedRagCorpusId] = useState('')
  const [editedRagTopK, setEditedRagTopK] = useState<string>('')
  const [ragInfo, setRagInfo] = useState<RagInfo | null>(null)
  const [ragTesting, setRagTesting] = useState(false)
  const [hasSettingsChanges, setHasSettingsChanges] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)

  useEffect(() => {
    if (currentProjectId) {
      loadProjectData()
    }
  }, [currentProjectId])

  // Initialize the selector from project / global default, but ONLY when those
  // primitive values actually change. Previously this listed `currentProject`
  // itself in the deps, which caused every project reload (e.g. after creating
  // a chat) to clobber the user's manual selection.
  useEffect(() => {
    const modelToUse = currentProject?.default_model || settings.default_model
    setSelectedModel(modelToUse)
  }, [currentProject?.default_model, settings.default_model])

  // Initialize settings form when project loads
  useEffect(() => {
    if (currentProject) {
      setEditedName(currentProject.name)
      setEditedInstructions(currentProject.custom_instructions || '')
      setEditedDefaultModel(currentProject.default_model || '')
      setEditedTemperature(currentProject.temperature?.toString() || '')
      setEditedMaxTokens(currentProject.max_tokens?.toString() || '')
      setEditedAutoAttachAllFiles(currentProject.auto_attach_all_files)
      setEditedRagEnabled(!!currentProject.rag_enabled)
      setEditedRagServerUrl(currentProject.rag_server_url || '')
      setEditedRagCorpusId(currentProject.rag_corpus_id || '')
      setEditedRagTopK(currentProject.rag_top_k?.toString() || '')
      setRagInfo(null)
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
      const autoAttachChanged = editedAutoAttachAllFiles !== currentProject.auto_attach_all_files
      const ragEnabledChanged = editedRagEnabled !== !!currentProject.rag_enabled
      const ragUrlChanged = editedRagServerUrl !== (currentProject.rag_server_url || '')
      const ragCorpusChanged = editedRagCorpusId !== (currentProject.rag_corpus_id || '')
      const ragTopKChanged = editedRagTopK !== (currentProject.rag_top_k?.toString() || '')
      setHasSettingsChanges(
        nameChanged ||
          instructionsChanged ||
          modelChanged ||
          tempChanged ||
          tokensChanged ||
          autoAttachChanged ||
          ragEnabledChanged ||
          ragUrlChanged ||
          ragCorpusChanged ||
          ragTopKChanged
      )
    }
  }, [
    editedName,
    editedInstructions,
    editedDefaultModel,
    editedTemperature,
    editedMaxTokens,
    editedAutoAttachAllFiles,
    editedRagEnabled,
    editedRagServerUrl,
    editedRagCorpusId,
    editedRagTopK,
    currentProject,
  ])

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
        adjustChatCount(currentProjectId, 1)
        setCurrentChat(newChat)
        navigate(`/chats/${newChat.id}`)
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
    navigate(`/chats/${chat.id}`)
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
    const ok = await confirm({
      title: 'Delete this chat?',
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    await deleteChat(chatId)
    setProjectChats((prev) => prev.filter((chat) => chat.id !== chatId))
    if (currentProjectId) {
      adjustChatCount(currentProjectId, -1)
    }
  }

  const handleTestRagConnection = async () => {
    if (!currentProjectId) return
    const url = editedRagServerUrl.trim()
    if (!url) {
      showToast('Enter a RAG server URL first', 'warning')
      return
    }
    try {
      setRagTesting(true)
      const info = await ragApi.testConnection(currentProjectId, url)
      setRagInfo(info)
      if (editedRagCorpusId && !info.corpora.some((c) => c.id === editedRagCorpusId)) {
        setEditedRagCorpusId('')
      }
      if (!editedRagTopK) {
        setEditedRagTopK(info.default_top_k.toString())
      }
      showToast(
        `Connected to ${info.server_name} (embed: ${info.embedding_model})`,
        'success'
      )
    } catch (err) {
      console.error('RAG test connection failed:', err)
      const message = err instanceof Error ? err.message : 'RAG connection failed'
      showToast(message, 'error')
    } finally {
      setRagTesting(false)
    }
  }

  const handleSaveSettings = async () => {
    if (!currentProjectId || !currentProject) return

    if (!editedName.trim()) {
      showToast('Project name cannot be empty', 'warning')
      return
    }

    if (editedRagEnabled) {
      if (!editedRagServerUrl.trim()) {
        showToast('RAG server URL is required when RAG is enabled', 'warning')
        return
      }
      if (!editedRagCorpusId.trim()) {
        showToast('Select a corpus before enabling RAG', 'warning')
        return
      }
      const k = parseInt(editedRagTopK, 10)
      if (!Number.isFinite(k) || k < 1 || k > 50) {
        showToast('top_k must be a number between 1 and 50', 'warning')
        return
      }
    }

    try {
      setSavingSettings(true)

      const updated = await updateProject(currentProjectId, {
        name: editedName.trim(),
        custom_instructions: editedInstructions.trim() || undefined,
        default_model: editedDefaultModel.trim() || undefined,
        temperature: editedTemperature ? parseFloat(editedTemperature) : undefined,
        max_tokens: editedMaxTokens ? parseInt(editedMaxTokens, 10) : undefined,
        auto_attach_all_files: editedAutoAttachAllFiles,
        rag_enabled: editedRagEnabled,
        rag_server_url: editedRagServerUrl.trim() || null,
        rag_corpus_id: editedRagCorpusId.trim() || null,
        rag_top_k: editedRagTopK ? parseInt(editedRagTopK, 10) : null,
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
      setEditedAutoAttachAllFiles(currentProject.auto_attach_all_files)
      setEditedRagEnabled(!!currentProject.rag_enabled)
      setEditedRagServerUrl(currentProject.rag_server_url || '')
      setEditedRagCorpusId(currentProject.rag_corpus_id || '')
      setEditedRagTopK(currentProject.rag_top_k?.toString() || '')
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
        <Button onClick={() => navigate('/')} variant="primary">
          Back to Chats
        </Button>
      </div>
    )
  }

  // RAG corpus dropdown: live-from-server when ragInfo is set, otherwise show
  // the saved corpus as a single locked option so the stored config is legible
  // until the user re-tests the connection.
  const corpusOptions = ragInfo
    ? ragInfo.corpora
    : editedRagCorpusId
      ? [{ id: editedRagCorpusId, display_name: editedRagCorpusId, article_count: 0 }]
      : []
  const corpusDropdownDisabled = !editedRagEnabled || (!ragInfo && !editedRagCorpusId)
  const topKMax = ragInfo?.max_top_k ?? 50
  const topKPlaceholder = ragInfo ? `default ${ragInfo.default_top_k}` : 'e.g. 5'

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
                    type="text"
                    className="project-detail__input"
                    value={editedMaxTokens}
                    onChange={(e) => {
                      const value = e.target.value
                      // Allow empty string or positive integers only
                      if (value === '' || /^[1-9]\d*$/.test(value)) {
                        setEditedMaxTokens(value)
                      }
                    }}
                    placeholder={`Global default: ${settings.default_max_tokens}`}
                  />
                  <span className="project-detail__hint">
                    Maximum context window size
                  </span>
                </div>
              </div>

              {/* Auto-attach all files (Phase 6 UX hint) */}
              <div className="project-detail__field">
                <label className="project-detail__label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={editedAutoAttachAllFiles}
                    onChange={(e) => setEditedAutoAttachAllFiles(e.target.checked)}
                  />
                  Auto-attach all project files to new messages
                </label>
                <span className="project-detail__hint">
                  When on, every new message in this project pre-selects all
                  files in the attach picker. You can still deselect any of
                  them before sending.
                </span>
              </div>
            </div>

            {/* RAG Server */}
            <div className="project-detail__model-settings">
              <h3 className="project-detail__subsection-title">RAG Server</h3>
              <p className="project-detail__subsection-description">
                Connect this project to a retrieval-augmented generation server.
                When enabled, every user message is sent to the RAG server and
                the returned chunks are injected into the system prompt.
              </p>

              <div className="project-detail__field">
                <label className="project-detail__label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={editedRagEnabled}
                    onChange={(e) => setEditedRagEnabled(e.target.checked)}
                  />
                  Enable RAG for this project
                </label>
              </div>

              <div className="project-detail__field">
                <label htmlFor="rag-server-url" className="project-detail__label">
                  Server URL
                </label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    id="rag-server-url"
                    type="text"
                    className="project-detail__input"
                    value={editedRagServerUrl}
                    onChange={(e) => setEditedRagServerUrl(e.target.value)}
                    placeholder="http://host.docker.internal:8001"
                    maxLength={512}
                    disabled={!editedRagEnabled}
                    style={{ flex: 1 }}
                  />
                  <Button
                    onClick={handleTestRagConnection}
                    variant="secondary"
                    size="sm"
                    disabled={!editedRagEnabled || !editedRagServerUrl.trim() || ragTesting}
                  >
                    {ragTesting ? 'Testing…' : 'Test connection'}
                  </Button>
                </div>
                <span className="project-detail__hint">
                  Base URL of the RAG server. The backend runs in Docker, so use{' '}
                  <code>http://host.docker.internal:8001</code> to reach a server
                  on your host (not <code>127.0.0.1</code>).
                </span>
              </div>

              <div className="project-detail__field">
                <label htmlFor="rag-corpus" className="project-detail__label">
                  Corpus
                </label>
                <select
                  id="rag-corpus"
                  className="project-detail__select"
                  value={editedRagCorpusId}
                  onChange={(e) => setEditedRagCorpusId(e.target.value)}
                  disabled={corpusDropdownDisabled}
                >
                  <option value="">Select a corpus…</option>
                  {corpusOptions.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.display_name}
                      {c.article_count ? ` (${c.article_count.toLocaleString()})` : ''}
                    </option>
                  ))}
                </select>
                <span className="project-detail__hint">
                  {ragInfo
                    ? 'Pick the corpus to query for this project.'
                    : editedRagCorpusId
                      ? 'Saved corpus shown. Click Test connection to pick a different one.'
                      : 'Test the connection to populate this list.'}
                </span>
              </div>

              <div className="project-detail__field">
                <label htmlFor="rag-top-k" className="project-detail__label">
                  top_k
                </label>
                <input
                  id="rag-top-k"
                  type="number"
                  className="project-detail__input"
                  value={editedRagTopK}
                  onChange={(e) => setEditedRagTopK(e.target.value)}
                  placeholder={topKPlaceholder}
                  min="1"
                  max={topKMax}
                  step="1"
                  disabled={!editedRagEnabled}
                />
                <span className="project-detail__hint">
                  Number of chunks to retrieve per message (1–{topKMax}). Higher
                  values give the model more context but slow responses.
                </span>
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
