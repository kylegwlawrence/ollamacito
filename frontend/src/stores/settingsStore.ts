/**
 * Global Settings store (PLAN_NEW.md Phase 5).
 *
 * Replaces SettingsContext. The store auto-loads on first hydration via
 * `useSettingsAutoLoad()` (mount this from a top-level component like App).
 * Components subscribe with selectors:
 *
 *   const settings = useSettingsStore((s) => s.settings)
 *   const updateSettings = useSettingsStore((s) => s.updateSettings)
 */
import { create } from 'zustand'
import { useEffect } from 'react'
import { settingsApi } from '@/services/settingsApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { Settings } from '@/types'

// Sentinel value while we're still loading from the API. The frontend treats
// empty model strings as "use whatever the server returns".
const DEFAULT_SETTINGS: Settings = {
  user_id: '',
  default_model: '',
  conversation_summarization_model: '',
  default_temperature: 0.7,
  default_max_tokens: 2048,
  num_ctx: 2048,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

interface SettingsStore {
  settings: Settings
  loading: boolean
  error: string | null
  loaded: boolean
  refreshSettings: () => Promise<void>
  updateSettings: (updates: Partial<Settings>) => Promise<Settings | null>
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  settings: DEFAULT_SETTINGS,
  loading: true,
  error: null,
  loaded: false,
  refreshSettings: async () => {
    try {
      set({ loading: true, error: null })
      const data = await settingsApi.getGlobal()
      set({ settings: data, loaded: true })
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to load settings') })
    } finally {
      set({ loading: false })
    }
  },
  updateSettings: async (updates) => {
    try {
      set({ error: null })
      const data = await settingsApi.updateGlobal(updates)
      set({ settings: data })
      return data
    } catch (err) {
      set({ error: getErrorMessage(err, 'Failed to update settings') })
      return null
    }
  },
}))

/**
 * Mount once near the top of the tree to fetch settings on first paint.
 */
export const useSettingsAutoLoad = (): void => {
  const loaded = useSettingsStore((s) => s.loaded)
  const refresh = useSettingsStore((s) => s.refreshSettings)
  useEffect(() => {
    if (!loaded) {
      refresh()
    }
  }, [loaded, refresh])
}
