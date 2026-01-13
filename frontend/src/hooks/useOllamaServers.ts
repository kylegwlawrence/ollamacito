/**
 * React hook for managing Ollama servers
 */
import { useState, useEffect, useCallback } from 'react'
import type { OllamaServer, OllamaServerCreate, OllamaServerUpdate } from '../types/ollama_server'
import * as ollamaServerApi from '../services/ollamaServerApi'

interface UseOllamaServersReturn {
  servers: OllamaServer[]
  loading: boolean
  error: string | null
  loadServers: () => Promise<void>
  createServer: (data: OllamaServerCreate) => Promise<OllamaServer>
  updateServer: (serverId: string, data: OllamaServerUpdate) => Promise<OllamaServer>
  deleteServer: (serverId: string) => Promise<void>
  checkHealth: (serverId: string) => Promise<OllamaServer>
  getOnlineServers: () => OllamaServer[]
}

/**
 * Hook for managing Ollama servers with auto-refresh
 * @param autoRefreshInterval - Interval in milliseconds for auto-refresh (default: 60000ms = 1 minute)
 */
export function useOllamaServers(autoRefreshInterval: number = 60000): UseOllamaServersReturn {
  const [servers, setServers] = useState<OllamaServer[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  /**
   * Load all servers from API
   */
  const loadServers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await ollamaServerApi.listServers()
      setServers(data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load servers'
      setError(errorMessage)
      console.error('Error loading servers:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * Create a new server
   */
  const createServer = useCallback(
    async (data: OllamaServerCreate): Promise<OllamaServer> => {
      try {
        setError(null)
        const newServer = await ollamaServerApi.createServer(data)
        setServers((prev) => [...prev, newServer])
        return newServer
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to create server'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  /**
   * Update an existing server
   */
  const updateServer = useCallback(
    async (serverId: string, data: OllamaServerUpdate): Promise<OllamaServer> => {
      try {
        setError(null)
        const updatedServer = await ollamaServerApi.updateServer(serverId, data)
        setServers((prev) => prev.map((s) => (s.id === serverId ? updatedServer : s)))
        return updatedServer
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to update server'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  /**
   * Delete a server
   */
  const deleteServer = useCallback(async (serverId: string): Promise<void> => {
    try {
      setError(null)
      await ollamaServerApi.deleteServer(serverId)
      setServers((prev) => prev.filter((s) => s.id !== serverId))
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete server'
      setError(errorMessage)
      throw err
    }
  }, [])

  /**
   * Manually trigger health check for a server
   */
  const checkHealth = useCallback(
    async (serverId: string): Promise<OllamaServer> => {
      try {
        setError(null)
        const updatedServer = await ollamaServerApi.checkServerHealth(serverId)
        setServers((prev) => prev.map((s) => (s.id === serverId ? updatedServer : s)))
        return updatedServer
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to check server health'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  /**
   * Get list of online servers
   */
  const getOnlineServers = useCallback((): OllamaServer[] => {
    return servers.filter((s) => s.is_active && s.status === 'online')
  }, [servers])

  // Load servers on mount
  useEffect(() => {
    loadServers()
  }, [loadServers])

  // Auto-refresh servers at specified interval
  useEffect(() => {
    if (autoRefreshInterval <= 0) return

    const interval = setInterval(() => {
      loadServers()
    }, autoRefreshInterval)

    return () => clearInterval(interval)
  }, [autoRefreshInterval, loadServers])

  return {
    servers,
    loading,
    error,
    loadServers,
    createServer,
    updateServer,
    deleteServer,
    checkHealth,
    getOnlineServers,
  }
}
