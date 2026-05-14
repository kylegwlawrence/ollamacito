import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { useChatStore } from '@/stores/chatStore'
import { useProjectsStore } from '@/stores/projectsStore'
import { useStreaming } from '@/hooks/useStreaming'
import { useModels } from '@/hooks/useModels'
import { chatApi } from '@/services/chatApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { Project } from '@/types/project'
import { ViewHeader } from '../common/ViewHeader'
import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import './ChatContainer.css'

const projectHasFullRagConfig = (project: Project | null | undefined): boolean =>
  !!(
    project &&
    project.rag_enabled &&
    project.rag_server_id &&
    project.rag_top_k
  )

export const ChatContainer = () => {
  const { chatId } = useParams<{ chatId?: string }>()
  const navigate = useNavigate()

  const currentChat = useChatStore((s) => s.currentChat)
  const setCurrentChat = useChatStore((s) => s.setCurrentChat)
  const messages = useChatStore((s) => s.messages)
  const setMessages = useChatStore((s) => s.setMessages)
  const selectedFileIds = useChatStore((s) => s.selectedFileIds)
  const setSelectedFileIds = useChatStore((s) => s.setSelectedFileIds)
  const toggleFileId = useChatStore((s) => s.toggleFileId)
  const currentProject = useProjectsStore((s) => s.currentProject)
  const projects = useProjectsStore((s) => s.projects)
  const chatProject = currentChat?.project_id
    ? (projects.find((p) => p.id === currentChat.project_id) ?? currentProject)
    : null

  // Streaming now lives in a global store (see streamingStore.ts), so it
  // survives navigation: leaving the chat page mid-response no longer aborts
  // the fetch, and coming back shows the in-flight content again.
  const streaming = useStreaming()
  const isStreamingThisChat =
    streaming.isStreaming && streaming.activeChatId === currentChat?.id

  const { models } = useModels()
  const [togglingAgent, setTogglingAgent] = useState(false)
  const agentToggleAvailable = projectHasFullRagConfig(chatProject)

  const loadMessages = async (id: string) => {
    try {
      const chatData = await chatApi.get(id)
      setCurrentChat(chatData)
      setMessages(chatData.messages)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  // Sync store with URL: route param drives which chat is loaded.
  // Always refetch on chatId change — the sidebar may have pre-populated
  // `currentChat`, but the message list lives in the same store and would
  // otherwise show messages from the previous chat.
  useEffect(() => {
    if (chatId) {
      loadMessages(chatId)
    } else {
      setCurrentChat(null)
      setMessages([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId])

  // Get project files if chat belongs to a project
  const projectFiles =
    currentChat?.project_id && currentProject?.id === currentChat.project_id
      ? currentProject.files || []
      : undefined

  // Reset file selection when the chat (or its project) changes.
  // Phase 6: if the project opts into auto-attach-all, pre-select every file.
  useEffect(() => {
    if (!projectFiles || projectFiles.length === 0) {
      setSelectedFileIds([])
      return
    }
    if (currentProject?.auto_attach_all_files) {
      setSelectedFileIds(projectFiles.map((f) => f.id))
    } else {
      setSelectedFileIds([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChat?.id, currentProject?.id, currentProject?.auto_attach_all_files])

  const handleSend = (message: string, fileIds: string[]) => {
    if (!currentChat) return

    // Add user message to the message list immediately
    const userMessage = {
      id: `temp-${Date.now()}`,
      chat_id: currentChat.id,
      role: 'user' as const,
      content: message,
      created_at: new Date().toISOString(),
    }
    setMessages([...messages, userMessage])

    // Only route through the agent endpoint if both the toggle is on AND
    // the project actually supports it. Otherwise fall back to /stream so
    // the user never gets a confusing 400 if the toggle is stale.
    const useAgent =
      currentChat.agent_mode_enabled && agentToggleAvailable

    streaming.sendMessage(currentChat.id, message, fileIds, useAgent)
  }

  const handleToggleAgent = async () => {
    if (!currentChat || togglingAgent || !agentToggleAvailable) return
    const next = !currentChat.agent_mode_enabled
    setTogglingAgent(true)
    // Optimistically update so the UI reflects the change immediately.
    setCurrentChat({ ...currentChat, agent_mode_enabled: next })
    try {
      const updated = await chatApi.update(currentChat.id, {
        agent_mode_enabled: next,
      })
      setCurrentChat({ ...currentChat, ...updated })
    } catch (err) {
      // Roll back on failure.
      setCurrentChat({ ...currentChat, agent_mode_enabled: !next })
      console.error(
        'Failed to toggle agent mode:',
        getErrorMessage(err, 'unknown error')
      )
    } finally {
      setTogglingAgent(false)
    }
  }

  const handleChangeModel = async (newModel: string) => {
    if (!currentChat || newModel === currentChat.model) return
    try {
      const updated = await chatApi.update(currentChat.id, { model: newModel })
      setCurrentChat({ ...currentChat, ...updated })
    } catch (err) {
      console.error('Failed to change model:', getErrorMessage(err, 'unknown error'))
    }
  }

  if (!currentChat) {
    return (
      <main className="chat-container chat-container--empty" role="main" aria-label="Chat area">
        <div className="chat-container__empty-state">
          <h2>No chat selected</h2>
          <p>Create a new chat or select one from the sidebar</p>
        </div>
      </main>
    )
  }

  const agentToggleTooltip = agentToggleAvailable
    ? currentChat.agent_mode_enabled
      ? 'Disable agent mode (model can call search_wikipedia)'
      : 'Enable agent mode (let the model search Wikipedia on its own)'
    : 'Agent mode requires the chat’s project to have RAG configured'

  const modelOptions = models.map((m) => ({ value: m.name, label: m.name }))

  return (
    <main className="chat-container" role="main" aria-label="Chat conversation">
      <ViewHeader
        leading={
          currentChat.project_id ? (
            <button
              className="chat-container__back-btn"
              onClick={() => navigate(`/projects/${currentChat.project_id}`)}
              aria-label={`Back to ${chatProject?.name ?? 'project'}`}
              title={`Back to ${chatProject?.name ?? 'project'}`}
            >
              <Icon name="arrow_back" size={24} />
            </button>
          ) : undefined
        }
        title={currentChat.title}
        actions={
          <div className="chat-container__header-actions">
            <button
              type="button"
              className={`chat-container__agent-toggle${
                currentChat.agent_mode_enabled ? ' chat-container__agent-toggle--on' : ''
              }`}
              onClick={handleToggleAgent}
              disabled={!agentToggleAvailable || togglingAgent}
              title={agentToggleTooltip}
              aria-pressed={currentChat.agent_mode_enabled}
            >
              <Icon name="auto_awesome" size={16} />
              {currentChat.agent_mode_enabled ? 'Agent on' : 'Agent'}
            </button>
            <Select
              value={currentChat.model}
              onChange={handleChangeModel}
              options={modelOptions}
              aria-label="Change model for this chat"
            />
          </div>
        }
      />
      <MessageList
        messages={messages}
        isStreaming={isStreamingThisChat}
        streamingContent={isStreamingThisChat ? streaming.streamingContent : ''}
        streamingToolCalls={
          isStreamingThisChat ? streaming.streamingToolCalls : []
        }
      />
      <MessageInput
        onSend={handleSend}
        disabled={streaming.isStreaming}
        isStreaming={isStreamingThisChat}
        onStop={streaming.cancelStream}
        projectFiles={projectFiles}
        selectedFileIds={selectedFileIds}
        onToggleFile={toggleFileId}
      />
    </main>
  )
}
