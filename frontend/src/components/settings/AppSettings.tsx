import { useEffect, useState } from 'react'
import { useView } from '@/contexts/ViewContext'
import { useSettings } from '@/contexts/SettingsContext'
import { useToast } from '@/contexts/ToastContext'
import { useModels } from '@/hooks/useModels'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import './AppSettings.css'

export const AppSettings = () => {
  const { navigateToChat } = useView()
  const { settings, loading: settingsLoading, updateSettings } = useSettings()
  const { showToast } = useToast()
  const { models } = useModels()

  const [defaultModel, setDefaultModel] = useState<string>('')
  const [conversationSummarizationModel, setConversationSummarizationModel] = useState<string>('')
  const [temperature, setTemperature] = useState<string>('')
  const [maxTokens, setMaxTokens] = useState<string>('')
  const [numCtx, setNumCtx] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    if (settings) {
      setDefaultModel(settings.default_model || '')
      setConversationSummarizationModel(settings.conversation_summarization_model || '')
      setTemperature(settings.default_temperature?.toString() || '')
      setMaxTokens(settings.default_max_tokens?.toString() || '')
      setNumCtx(settings.num_ctx?.toString() || '')
    }
  }, [settings])

  useEffect(() => {
    if (settings) {
      const modelChanged = defaultModel !== settings.default_model
      const summarizationModelChanged = conversationSummarizationModel !== settings.conversation_summarization_model
      const tempChanged = temperature !== settings.default_temperature?.toString()
      const tokensChanged = maxTokens !== settings.default_max_tokens?.toString()
      const numCtxChanged = numCtx !== settings.num_ctx?.toString()
      setHasChanges(modelChanged || summarizationModelChanged || tempChanged || tokensChanged || numCtxChanged)
    }
  }, [defaultModel, conversationSummarizationModel, temperature, maxTokens, numCtx, settings])

  const handleSave = async () => {
    if (!settings) return

    try {
      setSaving(true)

      const updates = {
        default_model: defaultModel.trim() || undefined,
        conversation_summarization_model: conversationSummarizationModel.trim() || undefined,
        default_temperature: temperature ? parseFloat(temperature) : undefined,
        default_max_tokens: maxTokens ? parseInt(maxTokens, 10) : undefined,
        num_ctx: numCtx ? parseInt(numCtx, 10) : undefined,
      }

      const updated = await updateSettings(updates)

      if (updated) {
        setHasChanges(false)
        showToast('Application settings saved successfully!', 'success')
      } else {
        showToast('Failed to save application settings', 'error')
      }
    } catch (err) {
      console.error('Failed to save application settings:', err)
      showToast('Failed to save application settings', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    if (settings) {
      setDefaultModel(settings.default_model || '')
      setConversationSummarizationModel(settings.conversation_summarization_model || '')
      setTemperature(settings.default_temperature?.toString() || '')
      setMaxTokens(settings.default_max_tokens?.toString() || '')
      setNumCtx(settings.num_ctx?.toString() || '')
      setHasChanges(false)
    }
  }

  const handleBack = () => {
    if (hasChanges) {
      if (
        !window.confirm(
          'You have unsaved changes. Are you sure you want to leave?'
        )
      ) {
        return
      }
    }
    navigateToChat()
  }

  if (settingsLoading) {
    return (
      <div className="app-settings app-settings--loading">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="app-settings">
      {/* Header */}
      <div className="app-settings__header">
        <div className="app-settings__title-section">
          <button
            className="app-settings__back-button"
            onClick={handleBack}
            title="Back to chats"
          >
            ← Back
          </button>
          <h1 className="app-settings__title">Application Settings</h1>
        </div>
      </div>

      {/* Form */}
      <div className="app-settings__form">
        {/* Model Settings Section */}
        <div className="app-settings__section">
          <h3 className="app-settings__section-title">Model Configuration</h3>
          <p className="app-settings__section-description">
            Configure default models for the entire application. These settings apply to all new chats and projects unless overridden.
          </p>

          {/* Default Model */}
          <div className="app-settings__field">
            <label htmlFor="default-model" className="app-settings__label">
              Default Model
            </label>
            <select
              id="default-model"
              className="app-settings__select"
              value={defaultModel}
              onChange={(e) => setDefaultModel(e.target.value)}
            >
              {models.map((model) => (
                <option key={model.name} value={model.name}>
                  {model.name}
                </option>
              ))}
            </select>
            <span className="app-settings__hint">
              Model used for new chats and conversations
            </span>
          </div>

          {/* Conversation Summarization Model */}
          <div className="app-settings__field">
            <label htmlFor="summarization-model" className="app-settings__label">
              Conversation Summarization Model
            </label>
            <select
              id="summarization-model"
              className="app-settings__select"
              value={conversationSummarizationModel}
              onChange={(e) => setConversationSummarizationModel(e.target.value)}
            >
              {models.map((model) => (
                <option key={model.name} value={model.name}>
                  {model.name}
                </option>
              ))}
            </select>
            <span className="app-settings__hint">
              Model used for generating chat titles and summaries
            </span>
          </div>
        </div>

        {/* Generation Parameters Section */}
        <div className="app-settings__section">
          <h3 className="app-settings__section-title">Generation Parameters</h3>
          <p className="app-settings__section-description">
            Configure default parameters for text generation across all conversations.
          </p>

          {/* Temperature */}
          <div className="app-settings__field">
            <label htmlFor="temperature" className="app-settings__label">
              Temperature
            </label>
            <input
              id="temperature"
              type="number"
              className="app-settings__input"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              min="0"
              max="2"
              step="0.1"
            />
            <span className="app-settings__hint">
              Controls randomness (0.0-2.0). Lower = more focused, higher = more creative. Default: 0.7
            </span>
          </div>

          {/* Max Tokens */}
          <div className="app-settings__field">
            <label htmlFor="max-tokens" className="app-settings__label">
              Max Tokens
            </label>
            <input
              id="max-tokens"
              type="number"
              className="app-settings__input"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              min="1"
              step="1"
            />
            <span className="app-settings__hint">
              Maximum tokens for model output. Default: 2048
            </span>
          </div>

          {/* Context Window Size (num_ctx) */}
          <div className="app-settings__field">
            <label htmlFor="num-ctx" className="app-settings__label">
              Context Window Size (num_ctx)
            </label>
            <input
              id="num-ctx"
              type="number"
              className="app-settings__input"
              value={numCtx}
              onChange={(e) => setNumCtx(e.target.value)}
              min="1"
              step="1"
            />
            <span className="app-settings__hint">
              Context window size for the model (maximum tokens for input and output combined). Default: 2048
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="app-settings__actions">
          <div className="app-settings__actions-left">
            <Button
              onClick={handleSave}
              variant="primary"
              disabled={!hasChanges || saving}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              onClick={handleCancel}
              variant="secondary"
              disabled={!hasChanges || saving}
            >
              Cancel
            </Button>
          </div>
        </div>
      </div>

      {/* Info Section */}
      <div className="app-settings__info">
        <h3>About Application Settings</h3>
        <p>
          These settings define the default behavior for your entire application:
        </p>
        <ul>
          <li><strong>Default Model:</strong> The AI model used for new chats and conversations</li>
          <li><strong>Conversation Summarization Model:</strong> A smaller, faster model for generating chat titles</li>
          <li><strong>Temperature:</strong> Controls output randomness and creativity</li>
          <li><strong>Max Tokens:</strong> Limits the length of model responses</li>
          <li><strong>Context Window Size:</strong> Total tokens available for conversation history and responses</li>
        </ul>
        <p>
          Projects can override these defaults with their own settings.
        </p>
      </div>
    </div>
  )
}
