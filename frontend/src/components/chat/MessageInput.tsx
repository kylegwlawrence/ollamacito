import { useState, KeyboardEvent } from 'react'
import { Button } from '../common/Button'
import type { ProjectFile } from '@/types'
import './MessageInput.css'

interface MessageInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
  projectFiles?: ProjectFile[]
}

export const MessageInput = ({ onSend, disabled, isStreaming, onStop, projectFiles }: MessageInputProps) => {
  const [message, setMessage] = useState('')

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSend(message.trim())
      setMessage('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const hasFiles = projectFiles && projectFiles.length > 0

  return (
    <div className="message-input" role="form" aria-label="Message input">
      {/* Project Files Info Display */}
      {hasFiles && (
        <div className="message-input__project-files-info">
          <span className="message-input__files-badge">
            📁 {projectFiles.length} project file{projectFiles.length !== 1 ? 's' : ''} available as context
          </span>
        </div>
      )}

      <div className="message-input__controls">
        <textarea
          className="message-input__textarea"
          placeholder="Type your message... (Shift+Enter for new line)"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={3}
          aria-label="Type your message"
          aria-describedby="message-input-hint"
        />
        <div className="message-input__buttons">
          {isStreaming ? (
            <Button
              onClick={onStop}
              variant="secondary"
              className="message-input__stop-button"
              aria-label="Stop generating response"
            >
              Stop
            </Button>
          ) : (
            <Button
              onClick={handleSend}
              disabled={disabled || !message.trim()}
              variant="primary"
              aria-label="Send message"
            >
              Send
            </Button>
          )}
        </div>
      </div>
      <span id="message-input-hint" className="sr-only">
        Press Enter to send, Shift+Enter for new line
      </span>
    </div>
  )
}
