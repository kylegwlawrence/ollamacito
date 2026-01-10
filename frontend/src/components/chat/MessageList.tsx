import { useEffect, useRef } from 'react'
import { Message } from './Message'
import { LoadingSpinner } from '../common/LoadingSpinner'
import type { Message as MessageType } from '@/types'
import './MessageList.css'

interface MessageListProps {
  messages: MessageType[]
  isStreaming: boolean
  streamingContent: string
}

export const MessageList = ({ messages, isStreaming, streamingContent }: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  return (
    <div className="message-list">
      {messages.length === 0 && !isStreaming && (
        <div className="message-list__empty">
          <p>Start a conversation by sending a message below</p>
        </div>
      )}

      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}

      {isStreaming && streamingContent && (
        <div className="message message--assistant">
          <div className="message__content">
            <div className="message__text">{streamingContent}</div>
            <div className="message__meta">
              <LoadingSpinner size="sm" />
              <span>Generating...</span>
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}
