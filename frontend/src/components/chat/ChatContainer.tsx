import { useEffect } from 'react'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { useChat } from '@/contexts/ChatContext'
import { useStreaming } from '@/hooks/useStreaming'
import { chatApi } from '@/services/chatApi'
import './ChatContainer.css'

export const ChatContainer = () => {
  const { currentChat, messages, setMessages } = useChat()
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

    // Add user message to the message list immediately
    const userMessage = {
      id: `temp-${Date.now()}`, // Temporary ID, will be replaced when messages reload
      chat_id: currentChat.id,
      role: 'user' as const,
      content: message,
      created_at: new Date().toISOString(),
    }
    setMessages([...messages, userMessage])

    // Send to AI
    streaming.sendMessage(currentChat.id, message)
  }

  if (!currentChat) {
    return (
      <div className="chat-container chat-container--empty">
        <div className="chat-container__empty-state">
          <h2>No chat selected</h2>
          <p>Create a new chat or select one from the sidebar</p>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-container">
      <div className="chat-container__header">
        <h2>{currentChat.title}</h2>
        <span className="chat-container__model">{currentChat.model}</span>
      </div>
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
      />
    </div>
  )
}
