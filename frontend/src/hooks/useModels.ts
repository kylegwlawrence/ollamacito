import { useState, useEffect } from 'react'
import { ollamaApi } from '@/services/ollamaApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { OllamaModel } from '@/types/ollama'

export const useModels = () => {
  const [models, setModels] = useState<OllamaModel[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchModels = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await ollamaApi.listModels()
        setModels(response.models || [])
      } catch (err) {
        setError(getErrorMessage(err, 'Failed to load models'))
        setModels([])
      } finally {
        setLoading(false)
      }
    }

    fetchModels()
  }, [])

  return {
    models,
    loading,
    error,
  }
}
