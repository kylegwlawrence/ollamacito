import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDate } from '@/utils/formatters'
import type { Message as MessageType } from '@/types'
import './Message.css'

interface MessageProps {
  message: MessageType
}

export const Message = ({ message }: MessageProps) => {
  return (
    <div className={`message message--${message.role}`}>
      <div className="message__content">
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
