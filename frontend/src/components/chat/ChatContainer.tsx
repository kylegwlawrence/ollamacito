import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { useChatStore } from '@/stores/chatStore'
import { useProjectsStore } from '@/stores/projectsStore'
import { useStreaming } from '@/hooks/useStreaming'
import { chatApi } from '@/services/chatApi'
import './ChatContainer.css'

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

  const streaming = useStreaming(() => {
    // Reload messages after streaming completes
    if (currentChat) {
      loadMessages(currentChat.id)
    }
  })

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

    streaming.sendMessage(currentChat.id, message, fileIds)
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

  return (
    <main className="chat-container" role="main" aria-label="Chat conversation">
      <header className="chat-container__header">
        <div className="chat-container__header-left">
          {currentChat.project_id && (
            <button
              className="chat-container__back-button"
              onClick={() => navigate(`/projects/${currentChat.project_id}`)}
              title="Back to project"
              aria-label="Back to project"
            >
              ← Back to Project
            </button>
          )}
          <h2 className="chat-container__title">{currentChat.title}</h2>
        </div>
        <span className="chat-container__model" aria-label={`Using model ${currentChat.model}`}>
          {currentChat.model.split(':').map((part, index) => (
          <span key={index}>
            {part}
            {index < currentChat.model.split(':').length - 1 && <br />}
          </span>
          ))}
        </span>
      </header>
      <MessageList
        messages={messages}
        isStreaming={streaming.isStreaming}
        streamingContent={streaming.streamingContent}
      />
      <MessageInput
        onSend={handleSend}
        disabled={streaming.isStreaming}
        isStreaming={streaming.isStreaming}
        onStop={streaming.cancelStream}
        projectFiles={projectFiles}
        selectedFileIds={selectedFileIds}
        onToggleFile={toggleFileId}
      />
    </main>
  )
}
