/**
 * useCourseGeneration: drives the NDJSON stream for course generation and
 * exposes phase + research-trace + final-outline state to the UI.
 *
 * Owns: AbortController, accumulated frames, error state.
 *
 * Callers:
 *   const gen = useCourseGeneration()
 *   gen.start(courseId)                                          // /generate
 *   gen.regenerate(courseId, { input })                          // /regenerate
 *   gen.cancel()                                                 // abort
 *   gen.phase / gen.researchChunks / gen.toolCalls / gen.outline / ...
 */
import { useCallback, useRef, useState } from 'react'
import {
  streamCourseGenerate,
  streamCourseRegenerate,
} from '@/services/courseStreamApi'
import { useCourseStore } from '@/stores/courseStore'
import type {
  CourseOutline,
  CourseRegenerateRequest,
  CourseStatus,
  GenerationFrame,
  ValidationErrorEntry,
} from '@/types'

export type GenerationPhase =
  | 'idle'
  | 'research'
  | 'assembling'
  | 'done'
  | 'error'

export interface ResearchToolTrace {
  id: string
  name: string
  input: Record<string, unknown>
  status: 'pending' | 'ok' | 'error'
  summary?: string
  error?: string
}

interface UseCourseGenerationReturn {
  phase: GenerationPhase
  researchChunks: string
  toolCalls: ResearchToolTrace[]
  outline: CourseOutline | null
  validationErrors: ValidationErrorEntry[] | null
  finalStatus: CourseStatus | null
  error: string | null
  isStreaming: boolean
  start: (courseId: string) => Promise<void>
  regenerate: (courseId: string, body?: CourseRegenerateRequest) => Promise<void>
  cancel: () => void
  reset: () => void
}

export const useCourseGeneration = (): UseCourseGenerationReturn => {
  const [phase, setPhase] = useState<GenerationPhase>('idle')
  const [researchChunks, setResearchChunks] = useState('')
  const [toolCalls, setToolCalls] = useState<ResearchToolTrace[]>([])
  const [outline, setOutline] = useState<CourseOutline | null>(null)
  const [validationErrors, setValidationErrors] = useState<
    ValidationErrorEntry[] | null
  >(null)
  const [finalStatus, setFinalStatus] = useState<CourseStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)

  const controllerRef = useRef<AbortController | null>(null)
  const loadOne = useCourseStore((s) => s.loadOne)

  const reset = useCallback(() => {
    setPhase('idle')
    setResearchChunks('')
    setToolCalls([])
    setOutline(null)
    setValidationErrors(null)
    setFinalStatus(null)
    setError(null)
  }, [])

  const consume = useCallback(
    async (
      courseId: string,
      gen: AsyncGenerator<GenerationFrame, void, void>
    ) => {
      try {
        for await (const frame of gen) {
          switch (frame.type) {
            case 'phase':
              setPhase(frame.name)
              break
            case 'chunk':
              setResearchChunks((prev) => prev + frame.content)
              break
            case 'tool_call':
              setToolCalls((prev) => [
                ...prev,
                {
                  id: frame.id,
                  name: frame.name,
                  input: frame.input,
                  status: 'pending',
                },
              ])
              break
            case 'tool_result':
              setToolCalls((prev) =>
                prev.map((t) =>
                  t.id === frame.id
                    ? {
                        ...t,
                        status: frame.ok ? 'ok' : 'error',
                        summary: frame.summary,
                        error: frame.error,
                      }
                    : t
                )
              )
              break
            case 'outline':
              setOutline(frame.content)
              break
            case 'validation':
              setValidationErrors(frame.errors)
              break
            case 'done':
              setFinalStatus(frame.status)
              setPhase('done')
              break
            case 'error':
              setError(frame.message)
              setPhase('error')
              break
          }
        }
      } catch (err) {
        if ((err as DOMException)?.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Stream failed')
        setPhase('error')
      } finally {
        setIsStreaming(false)
        controllerRef.current = null
        // Refresh the course row so the UI sees persisted state on next render.
        loadOne(courseId).catch(() => {})
      }
    },
    [loadOne]
  )

  const start = useCallback(
    async (courseId: string) => {
      if (controllerRef.current) return
      reset()
      const controller = new AbortController()
      controllerRef.current = controller
      setIsStreaming(true)
      await consume(courseId, streamCourseGenerate(courseId, controller))
    },
    [consume, reset]
  )

  const regenerate = useCallback(
    async (courseId: string, body?: CourseRegenerateRequest) => {
      if (controllerRef.current) return
      reset()
      const controller = new AbortController()
      controllerRef.current = controller
      setIsStreaming(true)
      await consume(
        courseId,
        streamCourseRegenerate(courseId, body ?? {}, controller)
      )
    },
    [consume, reset]
  )

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  return {
    phase,
    researchChunks,
    toolCalls,
    outline,
    validationErrors,
    finalStatus,
    error,
    isStreaming,
    start,
    regenerate,
    cancel,
    reset,
  }
}
