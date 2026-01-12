import { useState, KeyboardEvent } from 'react'
import { Button } from '../common/Button'
import type { ProjectFile } from '@/types'
import './MessageInput.css'

interface MessageInputProps {
  onSend: (message: string, fileIds?: string[]) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
  projectFiles?: ProjectFile[]
}

export const MessageInput = ({ onSend, disabled, isStreaming, onStop, projectFiles }: MessageInputProps) => {
  const [message, setMessage] = useState('')
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([])
  const [showFilePicker, setShowFilePicker] = useState(false)

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSend(message.trim(), selectedFileIds.length > 0 ? selectedFileIds : undefined)
      setMessage('')
      setSelectedFileIds([])
      setShowFilePicker(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleFileSelection = (fileId: string) => {
    setSelectedFileIds((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    )
  }

  const getSelectedFiles = () => {
    if (!projectFiles) return []
    return projectFiles.filter((file) => selectedFileIds.includes(file.id))
  }

  const hasFiles = projectFiles && projectFiles.length > 0

  return (
    <div className="message-input" role="form" aria-label="Message input">
      {/* Selected Files Display */}
      {selectedFileIds.length > 0 && (
        <div className="message-input__selected-files">
          {getSelectedFiles().map((file) => (
            <button
              key={file.id}
              className="message-input__file-chip"
              onClick={() => toggleFileSelection(file.id)}
              type="button"
            >
              <span>📎 {file.filename}</span>
              <span className="message-input__file-chip-remove">×</span>
            </button>
          ))}
        </div>
      )}

      {/* File Picker Dropdown */}
      {showFilePicker && hasFiles && (
        <div className="message-input__file-picker">
          <div className="message-input__file-picker-header">
            <span>Select files to attach</span>
            <button
              className="message-input__file-picker-close"
              onClick={() => setShowFilePicker(false)}
              type="button"
            >
              ×
            </button>
          </div>
          <div className="message-input__file-list">
            {projectFiles.map((file) => (
              <label key={file.id} className="message-input__file-option">
                <input
                  type="checkbox"
                  checked={selectedFileIds.includes(file.id)}
                  onChange={() => toggleFileSelection(file.id)}
                />
                <span className="message-input__file-name">
                  {file.file_type === 'txt' && '📄'}
                  {file.file_type === 'json' && '📋'}
                  {file.file_type === 'csv' && '📊'}
                  {' '}
                  {file.filename}
                </span>
              </label>
            ))}
          </div>
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
          {hasFiles && (
            <Button
              onClick={() => setShowFilePicker(!showFilePicker)}
              variant="secondary"
              size="sm"
              disabled={disabled || isStreaming}
              aria-label="Attach files"
            >
              📎 {selectedFileIds.length > 0 ? `(${selectedFileIds.length})` : ''}
            </Button>
          )}
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
