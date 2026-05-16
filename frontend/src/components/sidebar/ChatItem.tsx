import { useState } from 'react'
import type { Chat } from '@/types'
import { Icon } from '../common/Icon'
import './ChatItem.css'

interface ChatItemProps {
  chat: Chat
  isActive: boolean
  onSelect: (chat: Chat) => void
  onRename: (chatId: string, newTitle: string) => Promise<void>
  onDelete: (chatId: string) => Promise<void>
}

export const ChatItem = ({ chat, isActive, onSelect, onRename, onDelete }: ChatItemProps) => {
  const [isEditing, setIsEditing] = useState(false)
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

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    await onDelete(chat.id)
  }

  return (
    <div
      className={`chat-item ${isActive ? 'chat-item--active' : ''}`}
      onClick={() => !isEditing && onSelect(chat)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (!isEditing && (e.key === 'Enter' || e.key === ' ')) {
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
            <span className="chat-item__model" title={chat.model}>
              {chat.model}
            </span>
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
