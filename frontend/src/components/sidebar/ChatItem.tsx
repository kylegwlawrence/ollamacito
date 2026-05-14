import { useState } from 'react'
import type { Chat } from '@/types'
import { useModels } from '@/hooks/useModels'
import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import './ChatItem.css'

interface ChatItemProps {
  chat: Chat
  isActive: boolean
  onSelect: (chat: Chat) => void
  onRename: (chatId: string, newTitle: string) => Promise<void>
  onChangeModel: (chatId: string, newModel: string) => Promise<void>
  onDelete: (chatId: string) => Promise<void>
}

export const ChatItem = ({ chat, isActive, onSelect, onRename, onChangeModel, onDelete }: ChatItemProps) => {
  const { models } = useModels()
  const [isEditing, setIsEditing] = useState(false)
  const [isSelectingModel, setIsSelectingModel] = useState(false)
  const [editTitle, setEditTitle] = useState(chat.title)

  const handleRename = async () => {
    if (editTitle.trim() && editTitle !== chat.title) {
      await onRename(chat.id, editTitle.trim())
    }
    setIsEditing(false)
    setEditTitle(chat.title)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleRename()
    } else if (e.key === 'Escape') {
      setIsEditing(false)
      setEditTitle(chat.title)
    }
  }

  const handleModelChange = async (newModel: string) => {
    if (newModel !== chat.model) {
      await onChangeModel(chat.id, newModel)
    }
    setIsSelectingModel(false)
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    await onDelete(chat.id)
  }

  const modelOptions = models.map((m) => ({ value: m.name, label: m.name }))

  return (
    <div
      className={`chat-item ${isActive ? 'chat-item--active' : ''}`}
      onClick={() => !isEditing && !isSelectingModel && onSelect(chat)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (!isEditing && !isSelectingModel && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onSelect(chat)
        }
      }}
      aria-label={`Chat: ${chat.title}, using model ${chat.model}`}
      aria-current={isActive ? 'page' : undefined}
    >
      {isEditing ? (
        <input
          autoFocus
          type="text"
          className="chat-item__input"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={handleRename}
          onKeyDown={handleKeyDown}
          onClick={(e) => e.stopPropagation()}
          aria-label="Edit chat title"
        />
      ) : isSelectingModel ? (
        <div className="chat-item__model-select" onClick={(e) => e.stopPropagation()}>
          <Select
            value={chat.model}
            onChange={handleModelChange}
            options={modelOptions}
            aria-label="Select model for chat"
            onClose={() => setIsSelectingModel(false)}
          />
        </div>
      ) : (
        <>
          <div
            className="chat-item__title"
            onDoubleClick={(e) => {
              e.stopPropagation()
              setIsEditing(true)
            }}
          >
            {chat.title}
          </div>
          <div className="chat-item__footer">
            <button
              className="chat-item__model-btn"
              onClick={(e) => {
                e.stopPropagation()
                setIsSelectingModel(true)
              }}
              aria-label={`Change model, currently ${chat.model}`}
            >
              {chat.model}
            </button>
            <div className="chat-item__actions">
              <button
                className="icon-btn chat-item__edit"
                onClick={(e) => {
                  e.stopPropagation()
                  setIsEditing(true)
                }}
                title="Rename chat"
                aria-label={`Rename chat ${chat.title}`}
              >
                <Icon name="edit" size={16} />
              </button>
              <button
                className="icon-btn chat-item__delete"
                onClick={handleDelete}
                title="Delete chat"
                aria-label={`Delete chat ${chat.title}`}
              >
                <Icon name="delete" size={16} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
