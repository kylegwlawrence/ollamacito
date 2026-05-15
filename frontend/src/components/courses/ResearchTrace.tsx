import { useState } from 'react'
import { Icon } from '../common/Icon'
import type { GenerationPhase, ResearchToolTrace } from '@/hooks/useCourseGeneration'
import './courses.css'

interface ResearchTraceProps {
  phase: GenerationPhase
  toolCalls: ResearchToolTrace[]
  notes: string
}

const PHASE_LABEL: Record<GenerationPhase, string> = {
  idle: 'Idle',
  research: 'Researching…',
  assembling: 'Assembling outline…',
  done: 'Done',
  error: 'Error',
}

const friendlyToolName = (n: string) =>
  n === 'search_wikipedia' ? 'Searched Wikipedia' : n

const summarizeInput = (input: Record<string, unknown>): string => {
  const q = input?.query
  if (typeof q === 'string' && q.trim()) return `"${q.trim()}"`
  try {
    return JSON.stringify(input)
  } catch {
    return ''
  }
}

export const ResearchTrace = ({
  phase,
  toolCalls,
  notes,
}: ResearchTraceProps) => {
  const isStreaming = phase === 'research' || phase === 'assembling'
  const [expanded, setExpanded] = useState(isStreaming)

  if (toolCalls.length === 0 && !notes && phase === 'idle') return null

  return (
    <div className="research-trace">
      <div
        className="research-trace__header"
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v)
        }}
      >
        <Icon name={expanded ? 'expand_more' : 'chevron_right'} size={16} />
        <span className="research-trace__phase">{PHASE_LABEL[phase]}</span>
        <span style={{ color: 'var(--on-surf-dim)' }}>
          {toolCalls.length === 1
            ? '1 tool call'
            : `${toolCalls.length} tool calls`}
        </span>
      </div>
      {expanded && (
        <>
          <ul className="research-trace__tools">
            {toolCalls.map((t) => (
              <li key={t.id} className="research-trace__tool">
                <Icon
                  name={
                    t.status === 'pending'
                      ? 'hourglass_empty'
                      : t.status === 'ok'
                        ? 'check_circle'
                        : 'error'
                  }
                  size={16}
                />
                <span>{friendlyToolName(t.name)}</span>
                <span style={{ color: 'var(--on-surf-dim)' }}>
                  {summarizeInput(t.input)}
                </span>
                {t.summary && (
                  <span style={{ color: 'var(--on-surf-dim)', marginLeft: 'auto' }}>
                    {t.summary}
                  </span>
                )}
                {t.error && (
                  <span style={{ color: 'var(--danger)', marginLeft: 'auto' }}>
                    {t.error}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {notes && <pre className="research-trace__notes">{notes}</pre>}
        </>
      )}
    </div>
  )
}
