import { useEffect } from 'react'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { useChat } from '@/contexts/ChatContext'
import { useProject } from '@/contexts/ProjectContext'
import { useView } from '@/contexts/ViewContext'
import { useStreaming } from '@/hooks/useStreaming'
import { chatApi } from '@/services/chatApi'
import './ChatContainer.css'

export const ChatContainer = () => {
  const { currentChat, messages, setMessages } = useChat()
  const { currentProject } = useProject()
  const { navigateToProject } = useView()
  const streaming = useStreaming(() => {
    // Reload messages after streaming completes
    if (currentChat) {
      loadMessages()
    }
  })

  const loadMessages = async () => {
    if (!currentChat) return
    try {
      const chatData = await chatApi.get(currentChat.id)
      setMessages(chatData.messages)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  useEffect(() => {
    if (currentChat) {
      loadMessages()
    } else {
      setMessages([])
    }
  }, [currentChat?.id])

  const handleSend = (message: string) => {
    if (!currentChat) return

    console.log('[ChatContainer] Sending message:', {
      chatId: currentChat.id,
      projectId: currentChat.project_id,
      hasProjectFiles: projectFiles && projectFiles.length > 0,
      fileCount: projectFiles?.length || 0,
    })

    // Add user message to the message list immediately
    const userMessage = {
      id: `temp-${Date.now()}`, // Temporary ID, will be replaced when messages reload
      chat_id: currentChat.id,
      role: 'user' as const,
      content: message,
      created_at: new Date().toISOString(),
    }
    setMessages([...messages, userMessage])

    // Send to AI (files are automatically included on backend for project chats)
    streaming.sendMessage(currentChat.id, message)
  }

  // Get project files if chat belongs to a project
  const projectFiles = currentChat?.project_id && currentProject?.id === currentChat.project_id
    ? currentProject.files || []
    : undefined

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
              onClick={() => navigateToProject(currentChat.project_id!)}
              title="Back to project"
              aria-label="Back to project"
            >
              ← Back to Project
            </button>
          )}
          <h2>{currentChat.title}</h2>
        </div>
        <span className="chat-container__model" aria-label={`Using model ${currentChat.model}`}>
          {currentChat.model}
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
      />
    </main>
  )
}
