/**
 * Server status badge component
 * Displays a colored indicator for server status
 */
import type { ServerStatus } from '../../types/ollama_server'
import './ServerStatusBadge.css'

interface ServerStatusBadgeProps {
  status: ServerStatus
  showLabel?: boolean
  size?: 'small' | 'medium' | 'large'
}

export function ServerStatusBadge({ status, showLabel = true, size = 'medium' }: ServerStatusBadgeProps) {
  const getStatusColor = (status: ServerStatus): string => {
    switch (status) {
      case 'online':
        return 'green'
      case 'offline':
        return 'red'
      case 'error':
        return 'orange'
      case 'unknown':
      default:
        return 'gray'
    }
  }

  const getStatusLabel = (status: ServerStatus): string => {
    return status.charAt(0).toUpperCase() + status.slice(1)
  }

  const color = getStatusColor(status)
  const label = getStatusLabel(status)

  return (
    <span className={`server-status-badge server-status-badge--${size}`}>
      <span className={`status-dot status-dot--${color}`} />
      {showLabel && <span className="status-label">{label}</span>}
    </span>
  )
}
