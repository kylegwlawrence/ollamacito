import { useEffect, useRef } from 'react'
import { Message } from './Message'
import { ToolCalls } from './ToolCalls'
import { LoadingSpinner } from '../common/LoadingSpinner'
import type { Message as MessageType } from '@/types'
import type { ToolCall } from '@/types/message'
import './MessageList.css'

interface MessageListProps {
  messages: MessageType[]
  isStreaming: boolean
  streamingContent: string
  streamingToolCalls?: ToolCall[]
}

export const MessageList = ({
  messages,
  isStreaming,
  streamingContent,
  streamingToolCalls = [],
}: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming, streamingContent, streamingToolCalls.length])

  const hasToolCalls = streamingToolCalls.length > 0

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

      {isStreaming && !streamingContent && !hasToolCalls && (
        <div className="message message--assistant">
          <div className="message__content">
            <div className="message__meta">
              <LoadingSpinner size="sm" />
              <span>Generating...</span>
            </div>
          </div>
        </div>
      )}

      {isStreaming && (streamingContent || hasToolCalls) && (
        <div className="message message--assistant">
          <div className="message__content">
            {hasToolCalls && (
              <ToolCalls calls={streamingToolCalls} streaming />
            )}
            {streamingContent && (
              <div className="message__text">{streamingContent}</div>
            )}
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
