import { useState } from 'react'
import { Button } from '../common/Button'
import { useToast } from '@/contexts/ToastContext'
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
  const { showToast } = useToast()

  const handleDelete = async (fileId: string, filename: string) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) {
      return
    }

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
        return '📄'
      case 'json':
        return '📋'
      case 'csv':
        return '📊'
      default:
        return '📎'
    }
  }

  if (files.length === 0) {
    return (
      <div className="file-list file-list--empty">
        <p>No files uploaded yet</p>
        <p className="file-list__hint">Upload .txt, .json, or .csv files to reference in your chats</p>
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
              <span className="file-item__icon">{getFileIcon(file.file_type)}</span>
              <div className="file-item__details">
                <span className="file-item__name">{file.filename}</span>
                <span className="file-item__meta">
                  {file.file_type.toUpperCase()} · {formatFileSize(file.file_size)}
                </span>
              </div>
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
              <div className="file-item__preview-label">Preview:</div>
              <pre className="file-item__preview-content">{file.content_preview}</pre>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
