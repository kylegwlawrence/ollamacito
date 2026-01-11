import { useEffect, useState } from 'react'
import { useView } from '@/contexts/ViewContext'
import { useProject } from '@/contexts/ProjectContext'
import { useToast } from '@/contexts/ToastContext'
import { projectApi } from '@/services/projectApi'
import { Button } from '../common/Button'
import { LoadingSpinner } from '../common/LoadingSpinner'
import './ProjectSettings.css'

export const ProjectSettings = () => {
  const { currentProjectId, navigateToProject, navigateToChat } = useView()
  const { currentProject, setCurrentProject, updateProject, deleteProject } = useProject()
  const { showToast } = useToast()

  const [name, setName] = useState('')
  const [customInstructions, setCustomInstructions] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    if (currentProjectId) {
      loadProject()
    }
  }, [currentProjectId])

  useEffect(() => {
    if (currentProject) {
      const nameChanged = name !== currentProject.name
      const instructionsChanged = customInstructions !== (currentProject.custom_instructions || '')
      setHasChanges(nameChanged || instructionsChanged)
    }
  }, [name, customInstructions, currentProject])

  const loadProject = async () => {
    if (!currentProjectId) return

    try {
      setLoading(true)
      setError(null)

      const project = await projectApi.get(currentProjectId)
      setCurrentProject(project)
      setName(project.name)
      setCustomInstructions(project.custom_instructions || '')
    } catch (err) {
      console.error('Failed to load project:', err)
      setError('Failed to load project')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!currentProjectId || !currentProject) return

    if (!name.trim()) {
      showToast('Project name cannot be empty', 'warning')
      return
    }

    try {
      setSaving(true)
      setError(null)

      const updated = await updateProject(currentProjectId, {
        name: name.trim(),
        custom_instructions: customInstructions.trim() || undefined,
      })

      if (updated) {
        // Preserve files array when updating project
        setCurrentProject({
          ...updated,
          files: currentProject.files,
        })
        setHasChanges(false)
        showToast('Project settings saved successfully!', 'success')
      }
    } catch (err) {
      console.error('Failed to save project:', err)
      setError('Failed to save project settings')
      showToast('Failed to save project settings', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!currentProjectId || !currentProject) return

    const chatCount = currentProject.chat_count || 0
    const confirmMessage =
      chatCount > 0
        ? `Are you sure you want to delete "${currentProject.name}" and its ${chatCount} chat(s)? This action cannot be undone.`
        : `Are you sure you want to delete "${currentProject.name}"? This action cannot be undone.`

    if (!window.confirm(confirmMessage)) return

    try {
      await deleteProject(currentProjectId)
      setCurrentProject(null)
      showToast('Project deleted successfully', 'success')
      navigateToChat()
    } catch (err) {
      console.error('Failed to delete project:', err)
      showToast('Failed to delete project', 'error')
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
    navigateToProject(currentProjectId!)
  }

  const handleCancel = () => {
    if (currentProject) {
      setName(currentProject.name)
      setCustomInstructions(currentProject.custom_instructions || '')
      setHasChanges(false)
    }
  }

  if (loading) {
    return (
      <div className="project-settings project-settings--loading">
        <LoadingSpinner />
      </div>
    )
  }

  if (error && !currentProject) {
    return (
      <div className="project-settings project-settings--error">
        <h2>Error</h2>
        <p>{error}</p>
        <Button onClick={() => navigateToChat()} variant="primary">
          Back to Chats
        </Button>
      </div>
    )
  }

  return (
    <div className="project-settings">
      {/* Header */}
      <div className="project-settings__header">
        <div className="project-settings__title-section">
          <button
            className="project-settings__back-button"
            onClick={handleBack}
            title="Back to project"
          >
            ← Back
          </button>
          <h1 className="project-settings__title">Project Settings</h1>
        </div>
      </div>

      {/* Form */}
      <div className="project-settings__form">
        {/* Project Name */}
        <div className="project-settings__field">
          <label htmlFor="project-name" className="project-settings__label">
            Project Name <span className="project-settings__required">*</span>
          </label>
          <input
            id="project-name"
            type="text"
            className="project-settings__input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter project name"
            maxLength={255}
          />
          <span className="project-settings__hint">
            {name.length}/255 characters
          </span>
        </div>

        {/* Custom Instructions */}
        <div className="project-settings__field">
          <label
            htmlFor="custom-instructions"
            className="project-settings__label"
          >
            Custom Instructions
          </label>
          <textarea
            id="custom-instructions"
            className="project-settings__textarea"
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value)}
            placeholder="Enter custom instructions for this project (optional)&#10;&#10;These instructions will be included in every chat within this project to guide the AI's behavior."
            rows={10}
          />
          <span className="project-settings__hint">
            These instructions will be sent with every message in project chats
          </span>
        </div>

        {/* Actions */}
        <div className="project-settings__actions">
          <div className="project-settings__actions-left">
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
          <Button onClick={handleDelete} variant="danger" disabled={saving}>
            Delete Project
          </Button>
        </div>
      </div>

      {/* Info Section */}
      <div className="project-settings__info">
        <h3>About Custom Instructions</h3>
        <p>
          Custom instructions are automatically included in every chat within
          this project. Use them to:
        </p>
        <ul>
          <li>Set the AI's tone, style, or personality for this project</li>
          <li>Define domain-specific knowledge or context</li>
          <li>Establish guidelines for how the AI should respond</li>
          <li>Reference uploaded files or documentation</li>
        </ul>
      </div>
    </div>
  )
}
