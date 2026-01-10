import { useEffect, useState } from 'react'
import { useChat } from '@/contexts/ChatContext'
import { useChats } from '@/hooks/useChats'
import { useSettings } from '@/contexts/SettingsContext'
import { useModels } from '@/hooks/useModels'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from './ChatItem'
import './Sidebar.css'

export const Sidebar = () => {
  const { currentChat, setCurrentChat } = useChat()
  const { chats, loading, loadChats, createChat, updateChat, deleteChat } = useChats()
  const { settings } = useSettings()
  const { models } = useModels()
  const [selectedModel, setSelectedModel] = useState<string>(settings.default_model)

  useEffect(() => {
    loadChats()
  }, [loadChats])

  useEffect(() => {
    setSelectedModel(settings.default_model)
  }, [settings.default_model])

  const handleNewChat = async () => {
    const newChat = await createChat({
      title: 'New Chat',
      model: selectedModel,
    })
    if (newChat) {
      setCurrentChat(newChat)
    }
  }

  const handleRename = async (chatId: string, newTitle: string) => {
    const updatedChat = await updateChat(chatId, { title: newTitle })
    if (updatedChat && currentChat?.id === chatId) {
      setCurrentChat(updatedChat)
    }
  }

  const handleChangeModel = async (chatId: string, newModel: string) => {
    const updatedChat = await updateChat(chatId, { model: newModel })
    if (updatedChat && currentChat?.id === chatId) {
      setCurrentChat(updatedChat)
    }
  }

  const handleDelete = async (chatId: string) => {
    if (window.confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
      await deleteChat(chatId)
      if (currentChat?.id === chatId) {
        setCurrentChat(null)
      }
    }
  }

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <h1 className="sidebar__title">Ollama::cito</h1>
        <Button
          onClick={handleNewChat}
          variant="primary"
          size="sm"
          title="Create a new chat"
        >
          + New Chat
        </Button>
        <div className="sidebar__model-selector">
          <label htmlFor="model-select" className="sidebar__model-label">
            Model:
          </label>
          <select
            id="model-select"
            className="sidebar__model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            title="Select a model for new chats"
          >
            {models.map((model) => (
              <option key={model.name} value={model.name}>
                {model.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="sidebar__chats">
        {loading && (
          <div className="sidebar__loading">
            <LoadingSpinner />
          </div>
        )}

        {!loading && chats.length === 0 && (
          <div className="sidebar__empty">
            <p>No chats yet. Create one to get started!</p>
          </div>
        )}

        {chats.map((chat) => (
          <ChatItem
            key={chat.id}
            chat={chat}
            isActive={currentChat?.id === chat.id}
            onSelect={setCurrentChat}
            onRename={handleRename}
            onChangeModel={handleChangeModel}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  )
}
