import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSettingsStore } from '@/stores/settingsStore'
import { useToastStore } from '@/stores/toastStore'
import { useThemeStore } from '@/stores/themeStore'
import { useModels } from '@/hooks/useModels'
import { useDebouncedCallback } from '@/hooks/useDebouncedCallback'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import type { Settings } from '@/types'
import './AppSettings.css'

const AUTOSAVE_DELAY_MS = 500

export const AppSettings = () => {
  const navigate = useNavigate()
  const settings = useSettingsStore((s) => s.settings)
  const settingsLoading = useSettingsStore((s) => s.loading)
  const updateSettings = useSettingsStore((s) => s.updateSettings)
  const showToast = useToastStore((s) => s.showToast)
  const { models } = useModels()
  const theme = useThemeStore((s) => s.theme)
  const setTheme = useThemeStore((s) => s.setTheme)

  const [defaultModel, setDefaultModel] = useState<string>('')
  const [conversationSummarizationModel, setConversationSummarizationModel] = useState<string>('')
  const [temperature, setTemperature] = useState<string>('')
  const [maxTokens, setMaxTokens] = useState<string>('')
  const [numCtx, setNumCtx] = useState<string>('')
  const [isSaving, setIsSaving] = useState(false)

  const parsedMaxTokens = maxTokens ? parseInt(maxTokens, 10) : NaN
  const parsedNumCtx = numCtx ? parseInt(numCtx, 10) : NaN
  const tokenBudgetError =
    Number.isFinite(parsedMaxTokens) &&
    Number.isFinite(parsedNumCtx) &&
    parsedMaxTokens >= parsedNumCtx
      ? 'Max Tokens must be less than the Context Window Size.'
      : null

  useEffect(() => {
    if (settings) {
      setDefaultModel(settings.default_model || '')
      setConversationSummarizationModel(settings.conversation_summarization_model || '')
      setTemperature(settings.default_temperature?.toString() || '')
      setMaxTokens(settings.default_max_tokens?.toString() || '')
      setNumCtx(settings.num_ctx?.toString() || '')
    }
  }, [settings])

  const persist = async (patch: Partial<Settings>) => {
    const updated = await updateSettings(patch)
    if (!updated) {
      showToast('Failed to save settings', 'error')
    }
  }

  const persistDebounced = useDebouncedCallback(persist, AUTOSAVE_DELAY_MS)

  const handleSave = async () => {
    persistDebounced.cancel()
    setIsSaving(true)
    const patch: Partial<Settings> = {}
    if (defaultModel) patch.default_model = defaultModel
    if (conversationSummarizationModel) patch.conversation_summarization_model = conversationSummarizationModel
    const parsedTemp = parseFloat(temperature)
    if (Number.isFinite(parsedTemp) && parsedTemp >= 0 && parsedTemp <= 2) {
      patch.default_temperature = parsedTemp
    }
    if (!tokenBudgetError) {
      const parsedMax = parseInt(maxTokens, 10)
      if (Number.isFinite(parsedMax) && parsedMax > 0) patch.default_max_tokens = parsedMax
    }
    const parsedCtx = parseInt(numCtx, 10)
    if (Number.isFinite(parsedCtx) && parsedCtx > 0) patch.num_ctx = parsedCtx
    const updated = await updateSettings(patch)
    setIsSaving(false)
    if (updated) {
      showToast('Settings saved', 'success')
    } else {
      showToast('Failed to save settings', 'error')
    }
  }

  // Numeric/text fields: update local state, validate, debounce-save when valid.
  const handleTemperatureChange = (value: string) => {
    setTemperature(value)
    if (!value) return
    const parsed = parseFloat(value)
    if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 2) {
      persistDebounced({ default_temperature: parsed })
    }
  }

  const handleMaxTokensChange = (value: string) => {
    setMaxTokens(value)
    if (!value) return
    const parsed = parseInt(value, 10)
    if (!Number.isFinite(parsed) || parsed <= 0) return
    // Block save (but keep local state) if the new value violates the
    // budget against the current num_ctx — the inline error explains why.
    const currentNumCtx = numCtx ? parseInt(numCtx, 10) : NaN
    if (Number.isFinite(currentNumCtx) && parsed >= currentNumCtx) return
    persistDebounced({ default_max_tokens: parsed })
  }

  const handleNumCtxChange = (value: string) => {
    setNumCtx(value)
    if (!value) return
    const parsed = parseInt(value, 10)
    if (!Number.isFinite(parsed) || parsed <= 0) return
    const currentMaxTokens = maxTokens ? parseInt(maxTokens, 10) : NaN
    if (Number.isFinite(currentMaxTokens) && currentMaxTokens >= parsed) return
    persistDebounced({ num_ctx: parsed })
  }

  // Selects: save immediately; cancel any pending debounced save first so it
  // doesn't clobber the new value on a slow burst.
  const handleDefaultModelChange = (value: string) => {
    setDefaultModel(value)
    persistDebounced.cancel()
    persist({ default_model: value || undefined })
  }

  const handleSummarizationModelChange = (value: string) => {
    setConversationSummarizationModel(value)
    persistDebounced.cancel()
    persist({ conversation_summarization_model: value || undefined })
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
          <button
            className="app-settings__back-btn"
            onClick={() => {
              persistDebounced.flush()
              navigate('/')
            }}
          >
            <Icon name="arrow_back" size={16} />
            Home
          </button>
        }
        title={
          <div className="app-settings__title-row">
            <span>Application Settings</span>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={isSaving || !!tokenBudgetError}
            >
              {isSaving ? 'Saving…' : 'Save Changes'}
            </Button>
          </div>
        }
      />

      <div className="app-settings__body">
        {/* Appearance */}
        <div className="card app-settings__section">
          <h3 className="app-settings__section-title">Appearance</h3>
          <div className="app-settings__field">
            <span className="app-settings__label">Theme</span>
            <div className="app-settings__theme-group" role="group" aria-label="Select theme">
              <button
                className={`app-settings__theme-btn${theme === 'light' ? ' app-settings__theme-btn--active' : ''}`}
                onClick={() => setTheme('light')}
                aria-pressed={theme === 'light'}
              >
                <Icon name="light_mode" size={16} />
                Light
              </button>
              <button
                className={`app-settings__theme-btn${theme === 'dark' ? ' app-settings__theme-btn--active' : ''}`}
                onClick={() => setTheme('dark')}
                aria-pressed={theme === 'dark'}
              >
                <Icon name="dark_mode" size={16} />
                Dark
              </button>
            </div>
          </div>
        </div>

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
              onChange={handleDefaultModelChange}
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
              onChange={handleSummarizationModelChange}
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
              onChange={(e) => handleTemperatureChange(e.target.value)}
              onBlur={() => persistDebounced.flush()}
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
              className={`app-settings__input${tokenBudgetError ? ' app-settings__input--invalid' : ''}`}
              value={maxTokens}
              onChange={(e) => handleMaxTokensChange(e.target.value)}
              onBlur={() => persistDebounced.flush()}
              min="1"
              step="1"
              aria-invalid={tokenBudgetError !== null}
              aria-describedby="max-tokens-hint max-tokens-error"
            />
            <span id="max-tokens-hint" className="app-settings__hint">
              Maximum tokens the model can generate in one response (Ollama&apos;s{' '}
              <code>num_predict</code>). Must be less than the context window size below,
              since the window is shared by your prompt and the reply. Default: 16384
            </span>
            {tokenBudgetError && (
              <span id="max-tokens-error" className="app-settings__error" role="alert">
                {tokenBudgetError}
              </span>
            )}
          </div>

          <div className="app-settings__field">
            <label htmlFor="num-ctx" className="app-settings__label">
              Context Window Size (num_ctx)
            </label>
            <input
              id="num-ctx"
              type="number"
              className={`app-settings__input${tokenBudgetError ? ' app-settings__input--invalid' : ''}`}
              value={numCtx}
              onChange={(e) => handleNumCtxChange(e.target.value)}
              onBlur={() => persistDebounced.flush()}
              min="1"
              step="1"
              aria-invalid={tokenBudgetError !== null}
            />
            <span className="app-settings__hint">
              Total tokens the model can hold at once — system prompt, conversation history,
              attached files, RAG hits, your message, and the generated reply all share this
              budget. Must be greater than Max Tokens. Default: 2048
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
            <li><strong>Max Tokens:</strong> Caps how many tokens the model can generate in a single response</li>
            <li><strong>Context Window Size:</strong> Total budget shared by the prompt (history, files, RAG) and the response — must be larger than Max Tokens</li>
          </ul>
          <p className="app-settings__section-description">
            Projects can override these defaults with their own settings.
          </p>
        </div>
      </div>
    </div>
  )
}
