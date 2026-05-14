/**
 * RAG servers store: user-owned saved (name, url, corpus_id) entries.
 *
 * Holds the full list (small — user-managed) and exposes CRUD actions that
 * sync with the backend. Mount `useRagServersAutoLoad()` from a top-level
 * component to hydrate on first paint, mirroring the projects/settings stores.
 */
import { create } from 'zustand'
import { useEffect } from 'react'
import { ragServerApi } from '@/services/ragServerApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { RagServer, RagServerCreate, RagServerUpdate } from '@/types'

interface RagServersStore {
  servers: RagServer[]
  loading: boolean
  loaded: boolean
  error: string | null

  load: () => Promise<void>
  create: (body: RagServerCreate) => Promise<RagServer | null>
  update: (id: string, body: RagServerUpdate) => Promise<RagServer | null>
  remove: (id: string) => Promise<void>
}

export const useRagServersStore = create<RagServersStore>((set) => ({
  servers: [],
  loading: true,
  loaded: false,
  error: null,

  load: async () => {
    try {
      set({ loading: true, error: null })
      const servers = await ragServerApi.list()
      set({ servers, loaded: true })
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to load RAG servers') })
    } finally {
      set({ loading: false })
    }
  },

  create: async (body) => {
    try {
      const created = await ragServerApi.create(body)
      set((s) => ({ servers: [...s.servers, created] }))
      return created
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to create RAG server') })
      throw err
    }
  },

  update: async (id, body) => {
    try {
      const updated = await ragServerApi.update(id, body)
      set((s) => ({
        servers: s.servers.map((s2) => (s2.id === id ? updated : s2)),
      }))
      return updated
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to update RAG server') })
      throw err
    }
  },

  remove: async (id) => {
    try {
      await ragServerApi.remove(id)
      set((s) => ({ servers: s.servers.filter((s2) => s2.id !== id) }))
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to delete RAG server') })
      throw err
    }
  },
}))

/** Mount once near the top to fetch RAG servers on first paint. */
export const useRagServersAutoLoad = (): void => {
  const loaded = useRagServersStore((s) => s.loaded)
  const load = useRagServersStore((s) => s.load)
  useEffect(() => {
    if (!loaded) {
      load()
    }
  }, [loaded, load])
}
