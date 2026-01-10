import { useEffect } from 'react'
import { useChat } from '@/contexts/ChatContext'
import { useChats } from '@/hooks/useChats'
import { useSettings } from '@/contexts/SettingsContext'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ChatItem } from './ChatItem'
import './Sidebar.css'

export const Sidebar = () => {
  const { currentChat, setCurrentChat } = useChat()
  const { chats, loading, loadChats, createChat, updateChat } = useChats()
  const { settings } = useSettings()

  useEffect(() => {
    loadChats()
  }, [loadChats])

  const handleNewChat = async () => {
    const newChat = await createChat({
      title: 'New Chat',
      model: settings.default_model,
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
          />
        ))}
      </div>
    </div>
  )
}
