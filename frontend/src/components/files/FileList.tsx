import { useState } from 'react'
import { Button } from '../common/Button'
import { Icon } from '../common/Icon'
import { useConfirmStore } from '@/stores/confirmStore'
import { useToastStore } from '@/stores/toastStore'
import { projectApi } from '@/services/projectApi'
import type { ProjectFile } from '@/types'
import './FileList.css'

interface FileListProps {
  projectId: string
  files: ProjectFile[]
  onFileDeleted: () => void
}

export const FileList = ({ projectId, files, onFileDeleted }: FileListProps) => {
  const [expandedFileId, setExpandedFileId] = useState<string | null>(null)
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null)
  const showToast = useToastStore((s) => s.showToast)
  const confirm = useConfirmStore((s) => s.ask)

  const handleDelete = async (fileId: string, filename: string) => {
    const ok = await confirm({
      title: `Delete "${filename}"?`,
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return

    try {
      setDeletingFileId(fileId)
      await projectApi.deleteFile(projectId, fileId)
      showToast(`File "${filename}" deleted`, 'success')
      onFileDeleted()
    } catch (error) {
      console.error('Failed to delete file:', error)
      showToast('Failed to delete file', 'error')
    } finally {
      setDeletingFileId(null)
    }
  }

  const toggleExpand = (fileId: string) => {
    setExpandedFileId(expandedFileId === fileId ? null : fileId)
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${Math.round(bytes / Math.pow(k, i))} ${sizes[i]}`
  }

  const getFileIcon = (fileType: string): string => {
    switch (fileType) {
      case 'txt':
        return 'description'
      case 'json':
        return 'data_object'
      case 'csv':
        return 'table_chart'
      default:
        return 'attach_file'
    }
  }

  if (files.length === 0) {
    return (
      <div className="file-list file-list--empty">
        <p>No files uploaded yet</p>
        <p className="file-list__hint">Upload .txt, .json, .csv, or .md files to reference in your chats</p>
      </div>
    )
  }

  return (
    <div className="file-list">
      {files.map((file) => (
        <div key={file.id} className="file-item">
          <div className="file-item__header">
            <button
              className="file-item__info"
              onClick={() => toggleExpand(file.id)}
              aria-expanded={expandedFileId === file.id}
            >
              <Icon name={getFileIcon(file.file_type)} size={20} className="file-item__icon" />
              <div className="file-item__details">
                <span className="file-item__name">{file.filename}</span>
                <span className="file-item__meta">
                  {file.file_type.toUpperCase()} · {formatFileSize(file.file_size)}
                </span>
              </div>
              <Icon
                name="expand_more"
                size={18}
                className={`file-item__chevron${expandedFileId === file.id ? ' file-item__chevron--open' : ''}`}
              />
            </button>
            <Button
              onClick={() => handleDelete(file.id, file.filename)}
              variant="danger"
              size="sm"
              disabled={deletingFileId === file.id}
            >
              {deletingFileId === file.id ? 'Deleting...' : 'Delete'}
            </Button>
          </div>

          {expandedFileId === file.id && file.content_preview && (
            <div className="file-item__preview">
              <div className="file-item__preview-label">Preview</div>
              <pre className="file-item__preview-content">{file.content_preview}</pre>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
