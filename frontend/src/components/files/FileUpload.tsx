import { useState, useRef, ChangeEvent } from 'react'
import { Button } from '../common/Button'
import { useToast } from '@/contexts/ToastContext'
import type { ProjectFileCreate } from '@/types'
import './FileUpload.css'

interface FileUploadProps {
  projectId: string
  onUploadSuccess: () => void
}

export const FileUpload = ({ projectId, onUploadSuccess }: FileUploadProps) => {
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()

  const handleFileSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    const fileExtension = file.name.split('.').pop()?.toLowerCase()
    if (!fileExtension || !['txt', 'json', 'csv'].includes(fileExtension)) {
      showToast('Only .txt, .json, and .csv files are supported', 'error')
      return
    }

    // Validate file size (max 5MB)
    const maxSize = 5 * 1024 * 1024
    if (file.size > maxSize) {
      showToast('File size must be less than 5MB', 'error')
      return
    }

    try {
      setUploading(true)

      // Read file content
      const content = await readFileContent(file)

      // Prepare file data
      const fileData: ProjectFileCreate = {
        filename: file.name,
        file_type: fileExtension as 'txt' | 'json' | 'csv',
        content,
      }

      // Upload to backend
      const { projectApi } = await import('@/services/projectApi')
      await projectApi.uploadFile(projectId, fileData)

      showToast(`File "${file.name}" uploaded successfully`, 'success')
      onUploadSuccess()

      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error) {
      console.error('File upload error:', error)
      showToast('Failed to upload file', 'error')
    } finally {
      setUploading(false)
    }
  }

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result
        if (typeof content === 'string') {
          resolve(content)
        } else {
          reject(new Error('Failed to read file content'))
        }
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsText(file)
    })
  }

  const handleButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="file-upload">
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.json,.csv"
        onChange={handleFileSelect}
        className="file-upload__input"
        disabled={uploading}
      />
      <Button
        onClick={handleButtonClick}
        variant="primary"
        size="sm"
        disabled={uploading}
      >
        {uploading ? 'Uploading...' : '+ Upload File'}
      </Button>
      <span className="file-upload__hint">Supports .txt, .json, .csv (max 5MB)</span>
    </div>
  )
}
