import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { settingsApi } from '@/services/settingsApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { Settings } from '@/types'

// Default settings to use if loading fails or is still in progress
const DEFAULT_SETTINGS: Settings = {
  id: 1,
  default_model: 'qwen2.5-coder:7b',
  default_temperature: 0.7,
  default_max_tokens: 2048,
  theme: 'dark',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

interface SettingsContextType {
  settings: Settings
  loading: boolean
  error: string | null
  refreshSettings: () => Promise<void>
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

export const SettingsProvider = ({ children }: { children: ReactNode }) => {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshSettings = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await settingsApi.getGlobal()
      setSettings(data)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load settings'))
      // Keep using default settings even if loading fails
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshSettings()
  }, [])

  return (
    <SettingsContext.Provider value={{ settings, loading, error, refreshSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

export const useSettings = () => {
  const context = useContext(SettingsContext)
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider')
  }
  return context
}
