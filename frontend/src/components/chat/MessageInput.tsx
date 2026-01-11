import { useState, KeyboardEvent } from 'react'
import { Button } from '../common/Button'
import './MessageInput.css'

interface MessageInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
}

export const MessageInput = ({ onSend, disabled, isStreaming, onStop }: MessageInputProps) => {
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

  return (
    <div className="message-input" role="form" aria-label="Message input">
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
      <span id="message-input-hint" className="sr-only">
        Press Enter to send, Shift+Enter for new line
      </span>
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
  )
}
