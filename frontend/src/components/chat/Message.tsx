import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDate } from '@/utils/formatters'
import type { Message as MessageType, RagCitations } from '@/types'
import { ToolCalls } from './ToolCalls'
import './Message.css'

interface MessageProps {
  message: MessageType
}

// Build the browser-facing article URL: `{base}/?wiki={corpus}&article={title}`.
// `server_base_url` is the URL the backend uses to call the RAG server, which is
// typically `host.docker.internal` from inside Docker — we rewrite that to
// `localhost` so the link resolves from the user's browser on the host.
const buildArticleUrl = (
  baseUrl: string,
  corpus: string,
  title: string
): string => {
  const browserBase = baseUrl
    .replace(/host\.docker\.internal/g, 'localhost')
    .replace(/\/$/, '')
  return `${browserBase}/?wiki=${encodeURIComponent(corpus)}&article=${encodeURIComponent(title)}`
}

const Sources = ({ citations }: { citations: RagCitations }) => {
  if (!citations.hits || citations.hits.length === 0) return null
  return (
    <div className="message__sources">
      <div className="message__sources-header">
        <span className="message__sources-title">Sources</span>
        {!citations.used_dense && (
          <span
            className="message__sources-badge"
            title="Semantic search was unavailable on the RAG server; results are keyword-only."
          >
            keyword-only
          </span>
        )}
      </div>
      <ul className="message__sources-list">
        {citations.hits.map((hit, i) => (
          <li key={i} className="message__sources-item">
            <a
              className="message__sources-link"
              href={buildArticleUrl(
                citations.server_base_url,
                citations.corpus,
                hit.title
              )}
              target="_blank"
              rel="noopener noreferrer"
            >
              {hit.title}
              {hit.section ? ` § ${hit.section}` : ''}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
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
        {message.tool_calls && message.tool_calls.length > 0 && (
          <ToolCalls calls={message.tool_calls} />
        )}
        {message.rag_citations && <Sources citations={message.rag_citations} />}
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
