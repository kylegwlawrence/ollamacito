/**
 * Server selector dropdown component
 * Allows users to select an Ollama server for their chat
 */
import { useState, useRef, useEffect } from 'react'
import type { OllamaServer } from '../../types/ollama_server'
import { ServerStatusBadge } from './ServerStatusBadge'
import './ServerSelector.css'

interface ServerSelectorProps {
  servers: OllamaServer[]
  selectedServerId: string | null
  onServerSelect: (serverId: string | null) => void
  showOnlyOnline?: boolean
  disabled?: boolean
}

export function ServerSelector({
  servers,
  selectedServerId,
  onServerSelect,
  showOnlyOnline = true,
  disabled = false,
}: ServerSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Filter servers based on showOnlyOnline flag
  const availableServers = showOnlyOnline
    ? servers.filter((s) => s.is_active && s.status === 'online')
    : servers.filter((s) => s.is_active)

  const selectedServer = servers.find((s) => s.id === selectedServerId)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen)
    }
  }

  const handleSelect = (serverId: string) => {
    onServerSelect(serverId)
    setIsOpen(false)
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onServerSelect(null)
    setIsOpen(false)
  }

  return (
    <div className={`server-selector ${disabled ? 'server-selector--disabled' : ''}`} ref={dropdownRef}>
      <button
        type="button"
        className="server-selector__button"
        onClick={handleToggle}
        disabled={disabled}
      >
        <div className="server-selector__selected">
          {selectedServer ? (
            <>
              <ServerStatusBadge status={selectedServer.status} showLabel={false} size="small" />
              <span className="server-selector__name">{selectedServer.name}</span>
              <span className="server-selector__models">({selectedServer.models_count} models)</span>
            </>
          ) : (
            <span className="server-selector__placeholder">
              {availableServers.length > 0 ? 'Select server...' : 'No servers available'}
            </span>
          )}
        </div>
        {selectedServer && !disabled && (
          <button
            type="button"
            className="server-selector__clear"
            onClick={handleClear}
            title="Clear selection"
          >
            ×
          </button>
        )}
        <span className={`server-selector__arrow ${isOpen ? 'server-selector__arrow--up' : ''}`}>
          ▼
        </span>
      </button>

      {isOpen && availableServers.length > 0 && (
        <div className="server-selector__dropdown">
          {availableServers.map((server) => (
            <button
              key={server.id}
              type="button"
              className={`server-selector__option ${
                server.id === selectedServerId ? 'server-selector__option--selected' : ''
              }`}
              onClick={() => handleSelect(server.id)}
            >
              <div className="server-selector__option-main">
                <ServerStatusBadge status={server.status} showLabel={false} size="small" />
                <span className="server-selector__option-name">{server.name}</span>
              </div>
              <div className="server-selector__option-details">
                <span className="server-selector__option-models">{server.models_count} models</span>
                {server.average_response_time_ms && (
                  <span className="server-selector__option-latency">
                    {server.average_response_time_ms}ms
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
