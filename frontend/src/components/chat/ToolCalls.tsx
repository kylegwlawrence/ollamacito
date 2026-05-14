import { useState } from 'react'
import type { ToolCall } from '@/types/message'
import { Icon } from '../common/Icon'
import './ToolCalls.css'

interface ToolCallsProps {
  calls: ToolCall[]
  /** When true, render the "in flight" indicator on calls without a result yet. */
  streaming?: boolean
}

const friendlyToolName = (name: string): string => {
  if (name === 'search_wikipedia') return 'Searched Wikipedia'
  return name
}

const summarizeInput = (input: Record<string, unknown>): string => {
  // search_wikipedia is the only tool today; show its query string. Fall back
  // to a JSON dump for any future tool until it gets a dedicated formatter.
  const query = input?.query
  if (typeof query === 'string' && query.trim()) {
    return `"${query.trim()}"`
  }
  try {
    return JSON.stringify(input)
  } catch {
    return ''
  }
}

/**
 * Renders the tool calls an assistant made during one agentic turn.
 *
 * Layout mirrors the existing <Sources> block: a header + collapsible list.
 * Defaults to collapsed for persisted messages (history) and expanded
 * during streaming so the user can watch the agent work.
 */
export const ToolCalls = ({ calls, streaming = false }: ToolCallsProps) => {
  const [expanded, setExpanded] = useState(streaming)
  if (!calls || calls.length === 0) return null

  return (
    <div className="message__tool-calls">
      <button
        type="button"
        className="message__tool-calls-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="message__tool-calls-title">
          {calls.length === 1
            ? '1 tool call'
            : `${calls.length} tool calls`}
        </span>
        <Icon name="expand_more" size={16} className="message__tool-calls-chevron" />
      </button>
      {expanded && (
        <ul className="message__tool-calls-list">
          {calls.map((tc) => {
            // Pending: tool_result hasn't arrived yet (only in streaming mode).
            const pending = streaming && tc.summary === undefined && tc.error === undefined && tc.ok === false
            const status: 'ok' | 'err' | 'pending' = pending
              ? 'pending'
              : tc.ok
                ? 'ok'
                : 'err'
            return (
              <li
                key={tc.id}
                className={`message__tool-call message__tool-call--${status}`}
              >
                <span className="message__tool-call-name">
                  {friendlyToolName(tc.name)}
                </span>
                <span className="message__tool-call-arg">
                  {summarizeInput(tc.input)}
                </span>
                <span className="message__tool-call-status">
                  {status === 'pending' && (
                    <><Icon name="hourglass_empty" size={16} />…</>
                  )}
                  {status === 'ok' && (
                    <><Icon name="check_circle" size={16} />{tc.summary ?? 'ok'}</>
                  )}
                  {status === 'err' && (
                    <><Icon name="error" size={16} />{tc.error ?? 'failed'}</>
                  )}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
