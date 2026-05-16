import { useEffect, useState } from 'react'
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

const formatElapsed = (ms: number): string => {
  const total = Math.max(0, Math.round(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

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
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [endedAt, setEndedAt] = useState<number | null>(null)
  const [, forceTick] = useState(0)

  useEffect(() => {
    if (isStreaming) {
      setStartedAt(Date.now())
      setEndedAt(null)
    }
  }, [isStreaming])

  useEffect(() => {
    if (!isStreaming && startedAt && !endedAt) {
      setEndedAt(Date.now())
    }
  }, [isStreaming, startedAt, endedAt])

  useEffect(() => {
    if (!isStreaming) return
    const id = setInterval(() => forceTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [isStreaming])

  if (toolCalls.length === 0 && !notes && phase === 'idle') return null

  const elapsedMs =
    startedAt !== null ? (endedAt ?? Date.now()) - startedAt : null

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
        {elapsedMs !== null && (
          <span
            className="research-trace__timer"
            aria-live={isStreaming ? 'polite' : 'off'}
            aria-label={
              isStreaming
                ? `Elapsed time ${formatElapsed(elapsedMs)}`
                : `Completed in ${formatElapsed(elapsedMs)}`
            }
          >
            <Icon name="timer" size={16} />
            {formatElapsed(elapsedMs)}
          </span>
        )}
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
