import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDate } from '@/utils/formatters'
import type { Message as MessageType } from '@/types'
import './Message.css'

interface MessageProps {
  message: MessageType
}

export const Message = ({ message }: MessageProps) => {
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

  return (
    <div className={`message message--${message.role}`}>
      <div className="message__content">
        {/* Attached Files */}
        {message.attached_files && message.attached_files.length > 0 && (
          <div className="message__files">
            {message.attached_files.map((file) => (
              <div key={file.id} className="message__file-chip">
                <span className="message__file-icon">{getFileIcon(file.file_type)}</span>
                <span className="message__file-name">{file.filename}</span>
              </div>
            ))}
          </div>
        )}

        <div className="message__text">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        <div className="message__meta">
          <span className="message__time">{formatDate(message.created_at)}</span>
          {message.tokens_used && (
            <span className="message__tokens">{message.tokens_used} tokens</span>
          )}
        </div>
      </div>
    </div>
  )
}
