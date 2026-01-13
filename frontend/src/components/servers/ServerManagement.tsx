/**
 * Server management page
 * Full CRUD interface for managing Ollama servers
 */
import { useState } from 'react'
import { useOllamaServers } from '../../hooks/useOllamaServers'
import { ServerStatusBadge } from './ServerStatusBadge'
import type { OllamaServerCreate, OllamaServerUpdate } from '../../types/ollama_server'
import './ServerManagement.css'

export function ServerManagement() {
  const { servers, loading, error, createServer, updateServer, deleteServer, checkHealth } =
    useOllamaServers()

  const [showAddForm, setShowAddForm] = useState(false)
  const [editingServerId, setEditingServerId] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    tailscale_url: '',
    description: '',
    is_active: true,
  })

  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const resetForm = () => {
    setFormData({
      name: '',
      tailscale_url: '',
      description: '',
      is_active: true,
    })
    setFormError(null)
    setShowAddForm(false)
    setEditingServerId(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setSubmitting(true)

    try {
      if (editingServerId) {
        // Update existing server
        const updateData: OllamaServerUpdate = {}
        if (formData.name) updateData.name = formData.name
        if (formData.tailscale_url) updateData.tailscale_url = formData.tailscale_url
        if (formData.description) updateData.description = formData.description
        updateData.is_active = formData.is_active

        await updateServer(editingServerId, updateData)
      } else {
        // Create new server
        const createData: OllamaServerCreate = {
          name: formData.name,
          tailscale_url: formData.tailscale_url,
          description: formData.description || null,
          is_active: formData.is_active,
        }

        await createServer(createData)
      }

      resetForm()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save server')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (serverId: string) => {
    const server = servers.find((s) => s.id === serverId)
    if (!server) return

    setFormData({
      name: server.name,
      tailscale_url: server.tailscale_url,
      description: server.description || '',
      is_active: server.is_active,
    })
    setEditingServerId(serverId)
    setShowAddForm(true)
  }

  const handleDelete = async (serverId: string, serverName: string) => {
    if (
      !window.confirm(
        `Are you sure you want to delete server "${serverName}"? This action cannot be undone.`
      )
    ) {
      return
    }

    try {
      await deleteServer(serverId)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete server')
    }
  }

  const handleCheckHealth = async (serverId: string) => {
    try {
      await checkHealth(serverId)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to check server health')
    }
  }

  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp)
    return date.toLocaleString()
  }

  return (
    <div className="server-management">
      <div className="server-management__header">
        <h1>Ollama Server Management</h1>
        <p className="server-management__subtitle">
          Manage your distributed Ollama servers across your Tailscale network
        </p>
      </div>

      {error && (
        <div className="server-management__error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="server-management__actions">
        <button
          className="server-management__add-button"
          onClick={() => setShowAddForm(!showAddForm)}
          disabled={loading}
        >
          {showAddForm ? '✕ Cancel' : '+ Add Server'}
        </button>
      </div>

      {showAddForm && (
        <form className="server-management__form" onSubmit={handleSubmit}>
          <h2>{editingServerId ? 'Edit Server' : 'Add New Server'}</h2>

          {formError && <div className="form__error">{formError}</div>}

          <div className="form__group">
            <label htmlFor="server-name">Name *</label>
            <input
              id="server-name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., pop-os, raspberrypi6, macbook"
              required
              disabled={submitting}
            />
          </div>

          <div className="form__group">
            <label htmlFor="server-url">Tailscale URL *</label>
            <input
              id="server-url"
              type="text"
              value={formData.tailscale_url}
              onChange={(e) => setFormData({ ...formData, tailscale_url: e.target.value })}
              placeholder="e.g., http://pop-os.tailnet.ts.net:11434"
              required
              disabled={submitting}
            />
          </div>

          <div className="form__group">
            <label htmlFor="server-description">Description</label>
            <textarea
              id="server-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description..."
              rows={3}
              disabled={submitting}
            />
          </div>

          <div className="form__group form__group--checkbox">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                disabled={submitting}
              />
              <span>Active</span>
            </label>
          </div>

          <div className="form__actions">
            <button type="submit" className="form__submit" disabled={submitting}>
              {submitting ? 'Saving...' : editingServerId ? 'Update Server' : 'Create Server'}
            </button>
            <button type="button" className="form__cancel" onClick={resetForm} disabled={submitting}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="server-management__list">
        {loading && servers.length === 0 ? (
          <div className="server-management__loading">Loading servers...</div>
        ) : servers.length === 0 ? (
          <div className="server-management__empty">
            <p>No servers configured yet.</p>
            <p>Click "Add Server" to get started!</p>
          </div>
        ) : (
          <div className="server-cards">
            {servers.map((server) => (
              <div key={server.id} className="server-card">
                <div className="server-card__header">
                  <div className="server-card__title">
                    <h3>{server.name}</h3>
                    <ServerStatusBadge status={server.status} size="small" />
                  </div>
                  <div className="server-card__actions">
                    <button
                      className="server-card__action"
                      onClick={() => handleCheckHealth(server.id)}
                      title="Check health"
                    >
                      🔄
                    </button>
                    <button
                      className="server-card__action"
                      onClick={() => handleEdit(server.id)}
                      title="Edit"
                    >
                      ✏️
                    </button>
                    <button
                      className="server-card__action server-card__action--delete"
                      onClick={() => handleDelete(server.id, server.name)}
                      title="Delete"
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                <div className="server-card__body">
                  <div className="server-card__field">
                    <span className="server-card__label">URL:</span>
                    <span className="server-card__value">{server.tailscale_url}</span>
                  </div>

                  {server.description && (
                    <div className="server-card__field">
                      <span className="server-card__label">Description:</span>
                      <span className="server-card__value">{server.description}</span>
                    </div>
                  )}

                  <div className="server-card__stats">
                    <div className="server-card__stat">
                      <span className="server-card__stat-label">Models:</span>
                      <span className="server-card__stat-value">{server.models_count}</span>
                    </div>
                    {server.average_response_time_ms && (
                      <div className="server-card__stat">
                        <span className="server-card__stat-label">Response Time:</span>
                        <span className="server-card__stat-value">
                          {server.average_response_time_ms}ms
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="server-card__field">
                    <span className="server-card__label">Last Checked:</span>
                    <span className="server-card__value">
                      {formatTimestamp(server.last_checked_at)}
                    </span>
                  </div>

                  {server.last_error && (
                    <div className="server-card__error">
                      <strong>Error:</strong> {server.last_error}
                    </div>
                  )}

                  <div className="server-card__field">
                    <span className="server-card__label">Status:</span>
                    <span className="server-card__value">
                      {server.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
