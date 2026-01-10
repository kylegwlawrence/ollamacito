import { useState, useCallback } from 'react'
import { chatApi } from '@/services/chatApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { Chat, ChatCreate } from '@/types'

export const useChats = () => {
  const [chats, setChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadChats = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await chatApi.list()
      setChats(response.chats)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load chats'))
    } finally {
      setLoading(false)
    }
  }, [])

  const createChat = useCallback(async (chatData: ChatCreate): Promise<Chat | null> => {
    try {
      const newChat = await chatApi.create(chatData)
      setChats((prev) => [newChat, ...prev])
      return newChat
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create chat'))
      return null
    }
  }, [])

  const deleteChat = useCallback(async (chatId: string) => {
    try {
      await chatApi.delete(chatId)
      setChats((prev) => prev.filter((chat) => chat.id !== chatId))
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete chat'))
    }
  }, [])

  const updateChat = useCallback(async (chatId: string, updates: { title?: string; model?: string }): Promise<Chat | null> => {
    try {
      const updatedChat = await chatApi.update(chatId, updates)
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === chatId ? { ...chat, ...updatedChat } : chat
        )
      )
      return updatedChat
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to update chat'))
      return null
    }
  }, [])

  return {
    chats,
    loading,
    error,
    loadChats,
    createChat,
    deleteChat,
    updateChat,
  }
}
