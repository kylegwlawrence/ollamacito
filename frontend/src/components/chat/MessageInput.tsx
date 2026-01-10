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
    <div className="message-input">
      <textarea
        className="message-input__textarea"
        placeholder="Type your message... (Shift+Enter for new line)"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={3}
      />
      {isStreaming ? (
        <Button
          onClick={onStop}
          variant="secondary"
          className="message-input__stop-button"
        >
          Stop
        </Button>
      ) : (
        <Button
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          variant="primary"
        >
          Send
        </Button>
      )}
    </div>
  )
}
