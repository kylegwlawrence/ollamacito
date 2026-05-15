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
import { useRagServersStore } from '@/stores/ragServersStore'
import { useDebouncedCallback } from '@/hooks/useDebouncedCallback'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import { ChatItem } from '../sidebar/ChatItem'
import { FileUpload } from '../files/FileUpload'
import { FileList } from '../files/FileList'
import type { Chat, ProjectUpdate } from '@/types'
import './ProjectDetail.css'

const AUTOSAVE_DELAY_MS = 500

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
  const ragServers = useRagServersStore((s) => s.servers)
  const [projectChats, setProjectChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>(
    currentProject?.default_model || settings.default_model
  )

  // Settings form state
  const [editedName, setEditedName] = useState('')
  const [editedInstructions, setEditedInstructions] = useState('')
  const [editedDefaultModel, setEditedDefaultModel] = useState('')
  const [editedTemperature, setEditedTemperature] = useState('')
  const [editedMaxTokens, setEditedMaxTokens] = useState('')
  const [editedAutoAttachAllFiles, setEditedAutoAttachAllFiles] = useState(false)
  const [editedRagEnabled, setEditedRagEnabled] = useState(false)
  const [editedRagServerId, setEditedRagServerId] = useState<string>('')
  const [editedRagTopK, setEditedRagTopK] = useState<string>('')

  const [isSavingSettings, setIsSavingSettings] = useState(false)

  // Memory section state
  const [memoryDraft, setMemoryDraft] = useState('')
  const [isGeneratingMemory, setIsGeneratingMemory] = useState(false)
  const [savingMemory, setSavingMemory] = useState(false)

  useEffect(() => {
    if (currentProjectId) {
      loadProjectData()
    }
    // loadProjectData is a closure over state setters — including it here would
    // re-run the effect on every render. We only want to reload when the
    // project id changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProjectId])

  // Initialize the selector from project / global default, but ONLY when those
  // primitive values actually change. Previously this listed `currentProject`
  // itself in the deps, which caused every project reload (e.g. after creating
  // a chat) to clobber the user's manual selection.
  useEffect(() => {
    const modelToUse = currentProject?.default_model || settings.default_model
    setSelectedModel(modelToUse)
  }, [currentProject?.default_model, settings.default_model])

  // Initialize settings form when project loads.
  useEffect(() => {
    if (currentProject) {
      setEditedName(currentProject.name)
      setEditedInstructions(currentProject.custom_instructions || '')
      setEditedDefaultModel(currentProject.default_model || '')
      setEditedTemperature(currentProject.temperature?.toString() ?? settings.default_temperature.toString())
      setEditedMaxTokens(currentProject.max_tokens?.toString() ?? settings.default_max_tokens.toString())
      setEditedAutoAttachAllFiles(currentProject.auto_attach_all_files)
      setEditedRagEnabled(!!currentProject.rag_enabled)
      setEditedRagServerId(currentProject.rag_server_id || '')
      setEditedRagTopK(currentProject.rag_top_k?.toString() || '')
    }
    // `settings.default_temperature` / `settings.default_max_tokens` are read
    // here as fallbacks but intentionally omitted from the dep array —
    // including them would re-run this effect on every settings change and
    // clobber unsaved edits in the temperature / max_tokens fields. The
    // initialize-on-project-load semantics are what we want.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject])

  // Re-sync memory draft when the loaded project changes
  useEffect(() => {
    if (currentProject) {
      setMemoryDraft(currentProject.memory ?? '')
    }
  }, [currentProject])

  const persistProject = async (patch: ProjectUpdate) => {
    if (!currentProjectId || !currentProject) return
    try {
      const updated = await updateProject(currentProjectId, patch)
      if (updated) {
        setCurrentProject({ ...updated, files: currentProject.files })
      } else {
        showToast('Failed to save project settings', 'error')
      }
    } catch (err) {
      console.error('Failed to save project:', err)
      showToast('Failed to save project settings', 'error')
    }
  }

  const persistDebounced = useDebouncedCallback(persistProject, AUTOSAVE_DELAY_MS)

  const handleProjectSave = async () => {
    if (!currentProjectId || !currentProject) return
    persistDebounced.cancel()
    setIsSavingSettings(true)
    try {
      const patch: ProjectUpdate = {}
      if (editedName.trim()) patch.name = editedName.trim()
      patch.custom_instructions = editedInstructions.trim() || undefined
      patch.default_model = editedDefaultModel || undefined
      const parsedTemp = parseFloat(editedTemperature)
      if (Number.isFinite(parsedTemp)) patch.temperature = parsedTemp
      const parsedMax = parseInt(editedMaxTokens, 10)
      if (Number.isFinite(parsedMax) && parsedMax > 0) patch.max_tokens = parsedMax
      patch.auto_attach_all_files = editedAutoAttachAllFiles
      patch.rag_enabled = editedRagEnabled
      patch.rag_server_id = editedRagServerId || null
      const parsedTopK = parseInt(editedRagTopK, 10)
      patch.rag_top_k = Number.isFinite(parsedTopK) && parsedTopK >= 1 && parsedTopK <= 50 ? parsedTopK : null

      const updated = await updateProject(currentProjectId, patch)
      if (updated) {
        setCurrentProject({ ...updated, files: currentProject.files })
        showToast('Project settings saved', 'success')
      } else {
        showToast('Failed to save project settings', 'error')
      }
    } catch (err) {
      console.error('Failed to save project settings:', err)
      showToast('Failed to save project settings', 'error')
    } finally {
      setIsSavingSettings(false)
    }
  }

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

  // ----- Per-field autosave handlers -----

  const handleNameChange = (value: string) => {
    setEditedName(value)
    if (!value.trim()) return // never persist an empty project name
    persistDebounced({ name: value.trim() })
  }

  const handleInstructionsChange = (value: string) => {
    setEditedInstructions(value)
    persistDebounced({ custom_instructions: value.trim() || undefined })
  }

  const handleDefaultModelChange = (value: string) => {
    setEditedDefaultModel(value)
    persistDebounced.cancel()
    persistProject({ default_model: value.trim() || undefined })
  }

  const handleTemperatureChange = (value: string) => {
    setEditedTemperature(value)
    if (!value) return
    const parsed = parseFloat(value)
    if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 2) {
      persistDebounced({ temperature: parsed })
    }
  }

  const handleMaxTokensChange = (value: string) => {
    // Allow empty string or positive integers only (unchanged from legacy)
    if (value !== '' && !/^[1-9]\d*$/.test(value)) return
    setEditedMaxTokens(value)
    if (!value) return
    persistDebounced({ max_tokens: parseInt(value, 10) })
  }

  const handleAutoAttachAllFilesChange = (value: boolean) => {
    setEditedAutoAttachAllFiles(value)
    persistDebounced.cancel()
    persistProject({ auto_attach_all_files: value })
  }

  const handleRagEnabledChange = (value: boolean) => {
    setEditedRagEnabled(value)
    persistDebounced.cancel()
    persistProject({ rag_enabled: value })
    if (value && (!editedRagServerId || !editedRagTopK)) {
      showToast(
        'RAG enabled. Pick a server and set top_k to start retrieving.',
        'info',
      )
    }
  }

  const handleRagServerIdChange = (value: string) => {
    setEditedRagServerId(value)
    persistDebounced.cancel()
    persistProject({ rag_server_id: value || null })
  }

  const handleRagTopKChange = (value: string) => {
    setEditedRagTopK(value)
    if (!value) {
      persistDebounced({ rag_top_k: null })
      return
    }
    const parsed = parseInt(value, 10)
    if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 50) {
      persistDebounced({ rag_top_k: parsed })
    }
  }

  const handleGenerateMemory = async () => {
    if (!currentProjectId) return
    try {
      setIsGeneratingMemory(true)
      const generated = await projectApi.generateMemory(currentProjectId)
      setMemoryDraft(generated)
      showToast('Memory generated. Click Save to persist.', 'success')
    } catch (err) {
      console.error('Failed to generate memory:', err)
      const message = err instanceof Error ? err.message : 'Memory generation failed'
      showToast(message, 'error')
    } finally {
      setIsGeneratingMemory(false)
    }
  }

  const handleSaveMemory = async () => {
    if (!currentProjectId || !currentProject) return
    try {
      setSavingMemory(true)
      const updated = await updateProject(currentProjectId, {
        memory: memoryDraft.trim() ? memoryDraft : null,
      })
      if (updated) {
        setCurrentProject({
          ...updated,
          files: currentProject.files,
        })
        showToast('Memory saved', 'success')
      }
    } catch (err) {
      console.error('Failed to save memory:', err)
      showToast('Failed to save memory', 'error')
    } finally {
      setSavingMemory(false)
    }
  }

  const handleClearMemory = async () => {
    if (!currentProjectId || !currentProject) return
    const ok = await confirm({
      title: 'Clear project memory?',
      message: 'The saved memory document will be removed. This cannot be undone.',
      confirmLabel: 'Clear',
      variant: 'danger',
    })
    if (!ok) return
    try {
      const updated = await updateProject(currentProjectId, { memory: null })
      if (updated) {
        setCurrentProject({ ...updated, files: currentProject.files })
        setMemoryDraft('')
        showToast('Memory cleared', 'success')
      }
    } catch (err) {
      console.error('Failed to clear memory:', err)
      showToast('Failed to clear memory', 'error')
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

  // RAG server dropdown: list every server the user has saved globally.
  // The selected option may have been deleted out from under us — keep it in
  // the list as a stub so the stored config remains legible.
  const ragServerOptions = ragServers.map((s) => ({
    value: s.id,
    label: `${s.name} — ${s.corpus_id}`,
  }))
  if (
    editedRagServerId &&
    !ragServers.some((s) => s.id === editedRagServerId)
  ) {
    ragServerOptions.unshift({
      value: editedRagServerId,
      label: '(deleted server)',
    })
  }
  const topKPlaceholder = 'e.g. 5'

  const modelOptions = models.map((m) => ({
    value: m.name,
    label: m.name +
      (currentProject.default_model === m.name
        ? ' (Project Default)'
        : (!currentProject.default_model && settings.default_model === m.name
          ? ' (Global Default)'
          : '')),
  }))

  const defaultModelOptions = [
    { value: '', label: `Use Global Default (${settings.default_model})` },
    ...models.map((m) => ({ value: m.name, label: m.name })),
  ]

  return (
    <div className="project-detail">
      <ViewHeader
        breadcrumb={
          <button
            className="project-detail__home-btn"
            onClick={() => {
              persistDebounced.flush()
              navigate('/')
            }}
          >
            <Icon name="home" size={16} />
            Projects
          </button>
        }
        title={
          <div className="project-detail__title-row">
            {currentProject.name}
            <span className="project-detail__chat-chip">
              {projectChats.length} {projectChats.length === 1 ? 'chat' : 'chats'}
            </span>
          </div>
        }
      />

      <div className="project-detail__body">
        {/* Chats section */}
        <div className="card project-detail__section">
          <div className="project-detail__section-header">
            <div className="project-detail__chats-heading">
              <h2>Chats</h2>
              <div className="project-detail__chats-model-select">
                <Select
                  value={selectedModel}
                  onChange={setSelectedModel}
                  options={modelOptions}
                  aria-label="Select model for new chats"
                />
              </div>
            </div>
          </div>
          <div className="project-detail__chats-new-btn">
            <Button variant="primary" size="sm" leadingIcon="add" onClick={handleNewChat}>
              New chat
            </Button>
          </div>
          <div className="project-detail__chats">
            {projectChats.length === 0 ? null : (
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

        {/* Files section */}
        <div className="card project-detail__section">
          <div className="project-detail__section-header">
            <h2>Files</h2>
          </div>
          <div className="project-detail__chats-new-btn">
            <FileUpload projectId={currentProjectId!} onUploadSuccess={loadProjectData} />
          </div>
          <FileList
            projectId={currentProjectId!}
            files={currentProject.files || []}
            onFileDeleted={loadProjectData}
          />
        </div>

        {/* Settings (always expanded, between Files and Memory) */}
        <div className="card project-detail__settings-card">
          <div className="project-detail__settings-header">
            <Icon name="tune" size={18} />
            <h2 className="project-detail__settings-title">Project Settings</h2>
            <Button
              variant="primary"
              size="sm"
              onClick={handleProjectSave}
              disabled={isSavingSettings}
            >
              {isSavingSettings ? 'Saving…' : 'Save Changes'}
            </Button>
          </div>

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
                  onChange={(e) => handleNameChange(e.target.value)}
                  onBlur={() => persistDebounced.flush()}
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
                  onChange={(e) => handleInstructionsChange(e.target.value)}
                  onBlur={() => persistDebounced.flush()}
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
                    <span className="project-detail__label">Default Model</span>
                    <Select
                      value={editedDefaultModel}
                      onChange={handleDefaultModelChange}
                      options={defaultModelOptions}
                      aria-label="Select default model for project"
                    />
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
                      onChange={(e) => handleTemperatureChange(e.target.value)}
                      onBlur={() => persistDebounced.flush()}
                      min="0"
                      max="2"
                      step="0.1"
                    />
                    <span className="project-detail__hint">Controls randomness (0.0–2.0)</span>
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
                      onChange={(e) => handleMaxTokensChange(e.target.value)}
                      onBlur={() => persistDebounced.flush()}
                    />
                    <span className="project-detail__hint">Maximum context window size</span>
                  </div>
                </div>

                {/* Auto-attach switch */}
                <div className="project-detail__field">
                  <div className="project-detail__switch-row">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={editedAutoAttachAllFiles}
                      className={`switch${editedAutoAttachAllFiles ? ' switch--on' : ''}`}
                      onClick={() => handleAutoAttachAllFilesChange(!editedAutoAttachAllFiles)}
                    >
                      <span className="switch__thumb" />
                    </button>
                    <span className="project-detail__switch-text">
                      Auto-attach all project files to new messages
                    </span>
                  </div>
                  <span className="project-detail__hint">
                    When on, every new message in this project pre-selects all files.
                    You can still deselect any of them before sending.
                  </span>
                </div>
              </div>

              {/* RAG Server */}
              <div className="project-detail__model-settings">
                <h3 className="project-detail__subsection-title">RAG Server</h3>
                <p className="project-detail__subsection-description">
                  Pick a RAG server you&apos;ve configured globally. When enabled,
                  every user message is sent to that server and the returned
                  chunks are injected into the system prompt.{' '}
                  <button
                    type="button"
                    className="project-detail__inline-link"
                    onClick={() => navigate('/rag-servers')}
                  >
                    Manage RAG servers
                  </button>
                </p>

                <div className="project-detail__field">
                  <div className="project-detail__switch-row">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={editedRagEnabled}
                      className={`switch${editedRagEnabled ? ' switch--on' : ''}`}
                      onClick={() => handleRagEnabledChange(!editedRagEnabled)}
                    >
                      <span className="switch__thumb" />
                    </button>
                    <span className="project-detail__switch-text">
                      Enable RAG for this project
                    </span>
                  </div>
                </div>

                <div className="project-detail__field">
                  <span className="project-detail__label">RAG server</span>
                  {ragServers.length === 0 ? (
                    <span className="project-detail__hint">
                      You haven&apos;t added any RAG servers yet.{' '}
                      <button
                        type="button"
                        className="project-detail__inline-link"
                        onClick={() => navigate('/rag-servers')}
                      >
                        Add one
                      </button>{' '}
                      to enable RAG for this project.
                    </span>
                  ) : (
                    <>
                      <Select
                        value={editedRagServerId}
                        onChange={handleRagServerIdChange}
                        options={ragServerOptions}
                        placeholder="Select a RAG server…"
                        disabled={!editedRagEnabled}
                        aria-label="Select RAG server"
                      />
                      <span className="project-detail__hint">
                        Each option pairs a server with one corpus. Add or edit
                        entries on the RAG Servers page.
                      </span>
                    </>
                  )}
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
                    onChange={(e) => handleRagTopKChange(e.target.value)}
                    onBlur={() => persistDebounced.flush()}
                    placeholder={topKPlaceholder}
                    min="1"
                    max={50}
                    step="1"
                    disabled={!editedRagEnabled}
                  />
                  <span className="project-detail__hint">
                    Number of chunks to retrieve per message (1–50). Higher
                    values give the model more context but slow responses.
                  </span>
                </div>
              </div>
          </div>
        </div>

        {/* Memory section */}
        <div className="card project-detail__section">
          <div className="project-detail__section-header">
            <h2>Memory</h2>
            <div className="project-detail__header-actions">
              {(currentProject.memory ?? '') !== '' && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleClearMemory}
                  disabled={isGeneratingMemory || savingMemory}
                >
                  Clear
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={handleGenerateMemory}
                disabled={isGeneratingMemory || savingMemory}
              >
                {isGeneratingMemory ? 'Generating…' : 'Generate Memory'}
              </Button>
            </div>
          </div>
          <textarea
            className="project-detail__textarea project-detail__memory-textarea"
            value={memoryDraft}
            onChange={(e) => setMemoryDraft(e.target.value)}
            placeholder="No memory yet. Click 'Generate Memory' to extract key project facts and decisions from your chats, or type notes directly."
            rows={10}
            disabled={isGeneratingMemory}
          />
          <span className="project-detail__hint">
            Memory is injected at the top of every system prompt in this project's chats.
          </span>
          {memoryDraft !== (currentProject.memory ?? '') && (
            <div className="project-detail__settings-actions">
              <Button
                onClick={handleSaveMemory}
                variant="primary"
                size="sm"
                disabled={savingMemory}
              >
                {savingMemory ? 'Saving…' : 'Save Memory'}
              </Button>
              <Button
                onClick={() => setMemoryDraft(currentProject.memory ?? '')}
                variant="secondary"
                size="sm"
                disabled={savingMemory}
              >
                Discard
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
