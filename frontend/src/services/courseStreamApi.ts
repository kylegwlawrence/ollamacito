/**
 * Streaming client for course generation.
 *
 * Same NDJSON transport as streamApi.ts (chat agent), but with the course-
 * specific frame types defined in types/course.ts.
 *
 * Two endpoints:
 *   POST /api/v1/courses/{id}/generate
 *   POST /api/v1/courses/{id}/regenerate  (optionally with input override)
 */

import type {
  CourseRegenerateRequest,
  GenerationFrame,
} from '@/types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function* streamNdjson(
  url: string,
  body: object,
  controller: AbortController
): AsyncGenerator<GenerationFrame, void, void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
    credentials: 'include',
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    yield {
      type: 'error',
      message: `HTTP ${response.status}: ${text || response.statusText}`,
    }
    return
  }
  if (!response.body) {
    yield { type: 'error', message: 'Stream response has no body' }
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let nl: number
      while ((nl = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, nl).trim()
        buffer = buffer.slice(nl + 1)
        if (!line) continue
        try {
          yield JSON.parse(line) as GenerationFrame
        } catch {
          yield {
            type: 'error',
            message: `Malformed NDJSON frame: ${line}`,
          }
          return
        }
      }
    }
    const tail = buffer.trim()
    if (tail) {
      try {
        yield JSON.parse(tail) as GenerationFrame
      } catch {
        yield { type: 'error', message: `Malformed NDJSON tail: ${tail}` }
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* already released */
    }
  }
}

export function streamCourseGenerate(
  courseId: string,
  controller: AbortController
): AsyncGenerator<GenerationFrame, void, void> {
  return streamNdjson(
    `${API_URL}/api/v1/courses/${courseId}/generate`,
    {},
    controller
  )
}

export function streamCourseRegenerate(
  courseId: string,
  body: CourseRegenerateRequest,
  controller: AbortController
): AsyncGenerator<GenerationFrame, void, void> {
  return streamNdjson(
    `${API_URL}/api/v1/courses/${courseId}/regenerate`,
    body,
    controller
  )
}
