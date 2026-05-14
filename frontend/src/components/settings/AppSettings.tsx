import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useConfirmStore } from '@/stores/confirmStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useToastStore } from '@/stores/toastStore'
import { useModels } from '@/hooks/useModels'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import './AppSettings.css'

export const AppSettings = () => {
  const navigate = useNavigate()
  const settings = useSettingsStore((s) => s.settings)
  const settingsLoading = useSettingsStore((s) => s.loading)
  const updateSettings = useSettingsStore((s) => s.updateSettings)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)
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

  const handleBack = async () => {
    if (hasChanges) {
      const ok = await confirm({
        title: 'Discard unsaved changes?',
        message: 'You have unsaved changes that will be lost if you leave.',
        confirmLabel: 'Discard',
        variant: 'danger',
      })
      if (!ok) return
    }
    navigate('/')
  }

  if (settingsLoading) {
    return (
      <div className="app-settings app-settings--loading">
        <LoadingSpinner />
      </div>
    )
  }

  const modelOptions = models.map((m) => ({ value: m.name, label: m.name }))

  return (
    <div className="app-settings">
      <ViewHeader
        breadcrumb={
          <button className="app-settings__back-btn" onClick={handleBack}>
            <Icon name="arrow_back" size={16} />
            Home
          </button>
        }
        title="Application Settings"
        actions={
          hasChanges ? (
            <div className="app-settings__header-actions">
              <Button onClick={handleCancel} variant="secondary" size="sm" disabled={saving}>
                Cancel
              </Button>
              <Button onClick={handleSave} variant="primary" size="sm" disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          ) : undefined
        }
      />

      <div className="app-settings__body">
        {/* Model Configuration */}
        <div className="card app-settings__section">
          <h3 className="app-settings__section-title">Model Configuration</h3>
          <p className="app-settings__section-description">
            Configure default models for the entire application. These settings apply to all new
            chats and projects unless overridden.
          </p>

          <div className="app-settings__field">
            <span className="app-settings__label">Default Model</span>
            <Select
              value={defaultModel}
              onChange={setDefaultModel}
              options={modelOptions}
              aria-label="Select default model"
            />
            <span className="app-settings__hint">
              Model used for new chats and conversations
            </span>
          </div>

          <div className="app-settings__field">
            <span className="app-settings__label">Conversation Summarization Model</span>
            <Select
              value={conversationSummarizationModel}
              onChange={setConversationSummarizationModel}
              options={modelOptions}
              aria-label="Select summarization model"
            />
            <span className="app-settings__hint">
              Model used for generating chat titles and summaries
            </span>
          </div>
        </div>

        {/* Generation Parameters */}
        <div className="card app-settings__section">
          <h3 className="app-settings__section-title">Generation Parameters</h3>
          <p className="app-settings__section-description">
            Configure default parameters for text generation across all conversations.
          </p>

          <div className="app-settings__field">
            <label htmlFor="temperature" className="app-settings__label">Temperature</label>
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
              Controls randomness (0.0–2.0). Lower = more focused, higher = more creative.
              Default: 0.7
            </span>
          </div>

          <div className="app-settings__field">
            <label htmlFor="max-tokens" className="app-settings__label">Max Tokens</label>
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
              Context window size for the model (maximum tokens for input and output combined).
              Default: 2048
            </span>
          </div>
        </div>

        {/* About */}
        <div className="card app-settings__section">
          <h3 className="app-settings__section-title">About Application Settings</h3>
          <p className="app-settings__section-description">
            These settings define the default behavior for your entire application:
          </p>
          <ul className="app-settings__info-list">
            <li><strong>Default Model:</strong> The AI model used for new chats and conversations</li>
            <li><strong>Conversation Summarization Model:</strong> A smaller, faster model for generating chat titles</li>
            <li><strong>Temperature:</strong> Controls output randomness and creativity</li>
            <li><strong>Max Tokens:</strong> Limits the length of model responses</li>
            <li><strong>Context Window Size:</strong> Total tokens available for conversation history and responses</li>
          </ul>
          <p className="app-settings__section-description">
            Projects can override these defaults with their own settings.
          </p>
        </div>
      </div>
    </div>
  )
}
