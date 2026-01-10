import { createContext, useContext, useState, ReactNode } from 'react'
import type { Chat, Message } from '@/types'

interface ChatContextType {
  currentChat: Chat | null
  setCurrentChat: (chat: Chat | null) => void
  messages: Message[]
  setMessages: (messages: Message[]) => void
  isStreaming: boolean
  setIsStreaming: (isStreaming: boolean) => void
  streamingContent: string
  setStreamingContent: (content: string) => void
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export const ChatProvider = ({ children }: { children: ReactNode }) => {
  const [currentChat, setCurrentChat] = useState<Chat | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')

  return (
    <ChatContext.Provider
      value={{
        currentChat,
        setCurrentChat,
        messages,
        setMessages,
        isStreaming,
        setIsStreaming,
        streamingContent,
        setStreamingContent,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export const useChat = () => {
  const context = useContext(ChatContext)
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}
