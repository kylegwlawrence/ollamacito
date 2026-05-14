import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

import { Button } from '../common/Button'
import { Icon } from '../common/Icon'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ViewHeader } from '../common/ViewHeader'
import { useConfirmStore } from '@/stores/confirmStore'
import { useRagServersStore } from '@/stores/ragServersStore'
import { useToastStore } from '@/stores/toastStore'
import { ragServerApi } from '@/services/ragServerApi'
import { getErrorMessage } from '@/utils/errorHandler'
import type { RagServer, RagServerTestResult } from '@/types'
import './RagServersPage.css'

type FormState =
  | { mode: 'closed' }
  | { mode: 'create' }
  | { mode: 'edit'; server: RagServer }

export const RagServersPage = () => {
  const navigate = useNavigate()
  const servers = useRagServersStore((s) => s.servers)
  const loading = useRagServersStore((s) => s.loading)
  const createServer = useRagServersStore((s) => s.create)
  const updateServer = useRagServersStore((s) => s.update)
  const removeServer = useRagServersStore((s) => s.remove)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)

  const [form, setForm] = useState<FormState>({ mode: 'closed' })

  const handleDelete = async (server: RagServer) => {
    const ok = await confirm({
      title: `Delete "${server.name}"?`,
      message:
        'Projects currently using this RAG server will have their selection cleared.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await removeServer(server.id)
      showToast('RAG server deleted', 'success')
    } catch (err) {
      showToast(getErrorMessage(err, 'Failed to delete RAG server'), 'error')
    }
  }

  return (
    <div className="rag-servers">
      <ViewHeader
        breadcrumb={
          <button className="rag-servers__back-btn" onClick={() => navigate('/')}>
            <Icon name="arrow_back" size={16} />
            Home
          </button>
        }
        title="RAG Servers"
        actions={
          form.mode === 'closed' ? (
            <Button
              variant="primary"
              size="sm"
              leadingIcon="add"
              onClick={() => setForm({ mode: 'create' })}
            >
              Add Server
            </Button>
          ) : undefined
        }
      />

      <div className="rag-servers__body">
        <p className="rag-servers__description">
          Define each RAG corpus once here, then pick it from a project&apos;s
          settings dropdown. Each entry pairs a server URL with one corpus ID;
          add separate entries for each corpus you want to query (e.g.
          &quot;enwiki&quot; and &quot;simplewiki&quot;).
        </p>

        {form.mode !== 'closed' && (
          <RagServerForm
            initial={form.mode === 'edit' ? form.server : undefined}
            onCancel={() => setForm({ mode: 'closed' })}
            onSave={async (values) => {
              try {
                if (form.mode === 'edit') {
                  await updateServer(form.server.id, values)
                  showToast('RAG server updated', 'success')
                } else {
                  await createServer(values)
                  showToast('RAG server created', 'success')
                }
                setForm({ mode: 'closed' })
              } catch (err) {
                showToast(
                  getErrorMessage(err, 'Failed to save RAG server'),
                  'error',
                )
              }
            }}
          />
        )}

        {loading ? (
          <div className="rag-servers__loading">
            <LoadingSpinner />
          </div>
        ) : servers.length === 0 && form.mode === 'closed' ? (
          <div className="card rag-servers__empty">
            <p>You haven&apos;t added any RAG servers yet.</p>
            <Button
              variant="primary"
              size="sm"
              leadingIcon="add"
              onClick={() => setForm({ mode: 'create' })}
            >
              Add your first server
            </Button>
          </div>
        ) : (
          <div className="rag-servers__list">
            {servers.map((server) => (
              <RagServerRow
                key={server.id}
                server={server}
                onEdit={() => setForm({ mode: 'edit', server })}
                onDelete={() => handleDelete(server)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ----- Row -----

const parseHost = (url: string): string => {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

interface RowProps {
  server: RagServer
  onEdit: () => void
  onDelete: () => void
}

const RagServerRow = ({ server, onEdit, onDelete }: RowProps) => (
  <div className="card rag-servers__row">
    <div className="rag-servers__row-main">
      <div className="rag-servers__row-name">{server.name}</div>
      <div className="rag-servers__row-meta">
        <span>
          <Icon name="database" size={16} /> {server.corpus_id}
        </span>
        <span>
          <Icon name="dns" size={16} /> {parseHost(server.url)}
        </span>
      </div>
    </div>
    <div className="rag-servers__row-actions">
      <Button variant="ghost" size="sm" leadingIcon="edit" onClick={onEdit}>
        Edit
      </Button>
      <Button
        variant="ghost"
        size="sm"
        leadingIcon="delete"
        onClick={onDelete}
      >
        Delete
      </Button>
    </div>
  </div>
)

// ----- Form -----

interface FormValues {
  name: string
  url: string
  corpus_id: string
}

interface FormProps {
  initial?: RagServer
  onCancel: () => void
  onSave: (values: FormValues) => Promise<void>
}

const RagServerForm = ({ initial, onCancel, onSave }: FormProps) => {
  const [name, setName] = useState(initial?.name ?? '')
  const [url, setUrl] = useState(initial?.url ?? '')
  const [corpusId, setCorpusId] = useState(initial?.corpus_id ?? '')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<RagServerTestResult | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  const canSubmit = !!(name.trim() && url.trim() && corpusId.trim()) && !saving

  const handleTest = async () => {
    if (!url.trim() || !corpusId.trim()) return
    setTesting(true)
    setTestResult(null)
    setTestError(null)
    try {
      const result = await ragServerApi.test({
        url: url.trim(),
        corpus_id: corpusId.trim(),
      })
      setTestResult(result)
    } catch (err) {
      setTestError(getErrorMessage(err, 'Connection failed'))
    } finally {
      setTesting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSaving(true)
    try {
      await onSave({
        name: name.trim(),
        url: url.trim(),
        corpus_id: corpusId.trim(),
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="card rag-servers__form" onSubmit={handleSubmit}>
      <h3 className="rag-servers__form-title">
        {initial ? 'Edit RAG Server' : 'New RAG Server'}
      </h3>

      <div className="rag-servers__field">
        <label htmlFor="rag-name" className="rag-servers__label">
          Display name
        </label>
        <input
          id="rag-name"
          className="rag-servers__input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. enwiki"
          maxLength={100}
          required
        />
      </div>

      <div className="rag-servers__field">
        <label htmlFor="rag-url" className="rag-servers__label">
          Server URL
        </label>
        <input
          id="rag-url"
          className="rag-servers__input"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="http://127.0.0.1:8001"
          maxLength={512}
          required
        />
      </div>

      <div className="rag-servers__field">
        <label htmlFor="rag-corpus" className="rag-servers__label">
          Corpus ID
        </label>
        <input
          id="rag-corpus"
          className="rag-servers__input"
          value={corpusId}
          onChange={(e) => setCorpusId(e.target.value)}
          placeholder="e.g. simplewiki"
          maxLength={100}
          required
        />
      </div>

      <div className="rag-servers__form-actions">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          leadingIcon="network_check"
          onClick={handleTest}
          disabled={testing || !url.trim() || !corpusId.trim()}
        >
          {testing ? 'Testing…' : 'Test connection'}
        </Button>
        <div className="rag-servers__form-actions-right">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" size="sm" disabled={!canSubmit}>
            {saving ? 'Saving…' : initial ? 'Save changes' : 'Create'}
          </Button>
        </div>
      </div>

      {testError && (
        <div className="rag-servers__test-result rag-servers__test-result--error">
          <Icon name="error" size={16} /> {testError}
        </div>
      )}
      {testResult && (
        <div
          className={`rag-servers__test-result${
            testResult.corpus_found
              ? ' rag-servers__test-result--ok'
              : ' rag-servers__test-result--warn'
          }`}
        >
          {testResult.corpus_found ? (
            <Icon name="check_circle" size={16} />
          ) : (
            <Icon name="warning" size={16} />
          )}
          <div>
            <div>
              <strong>{testResult.server_name ?? 'RAG server reachable'}</strong>
              {testResult.server_version && ` v${testResult.server_version}`}
            </div>
            {testResult.corpus_found ? (
              <div>
                Corpus <code>{corpusId}</code> is available.
              </div>
            ) : (
              <div>
                Corpus <code>{corpusId}</code> not found. Available:{' '}
                {testResult.available_corpora.length === 0
                  ? '(none)'
                  : testResult.available_corpora.join(', ')}
              </div>
            )}
          </div>
        </div>
      )}
    </form>
  )
}
