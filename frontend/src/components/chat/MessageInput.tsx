import { useState, KeyboardEvent } from 'react'
import { Button } from '../common/Button'
import { Icon } from '../common/Icon'
import type { ProjectFile } from '@/types'
import './MessageInput.css'

interface MessageInputProps {
  onSend: (message: string, fileIds: string[]) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
  projectFiles?: ProjectFile[]
  selectedFileIds?: string[]
  onToggleFile?: (fileId: string) => void
}

export const MessageInput = ({
  onSend,
  disabled,
  isStreaming,
  onStop,
  projectFiles,
  selectedFileIds = [],
  onToggleFile,
}: MessageInputProps) => {
  const [message, setMessage] = useState('')

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSend(message.trim(), selectedFileIds)
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
      {/* Per-message file picker (Phase 6). Empty selection = no files attached. */}
      {hasFiles && (
        <div
          className="message-input__file-picker"
          role="group"
          aria-label="Attach project files"
        >
          <span className="message-input__file-picker-label">
            Attach files ({selectedFileIds.length}/{projectFiles.length}):
          </span>
          <div className="message-input__file-chips">
            {projectFiles.map((file) => {
              const isSelected = selectedFileIds.includes(file.id)
              return (
                <button
                  key={file.id}
                  type="button"
                  className={`message-input__file-chip${
                    isSelected ? ' message-input__file-chip--selected' : ''
                  }`}
                  onClick={() => onToggleFile?.(file.id)}
                  aria-pressed={isSelected}
                  title={
                    isSelected
                      ? `Detach ${file.filename}`
                      : `Attach ${file.filename}`
                  }
                  disabled={isStreaming}
                >
                  <Icon name={isSelected ? 'check' : 'add'} size={16} />
                  {file.filename}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <div className="message-input__pill">
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
        <div className="message-input__send-area">
          {isStreaming ? (
            <Button
              onClick={onStop}
              variant="danger"
              size="md"
              iconOnly
              leadingIcon="stop"
              aria-label="Stop generating response"
            />
          ) : (
            <Button
              onClick={handleSend}
              disabled={disabled || !message.trim()}
              variant="primary"
              size="md"
              iconOnly
              leadingIcon="arrow_upward"
              aria-label="Send message"
            />
          )}
        </div>
      </div>
      <span id="message-input-hint" className="sr-only">
        Press Enter to send, Shift+Enter for new line
      </span>
    </div>
  )
}
