/**
 * Tests for useCourseGeneration: stubs fetch with an NDJSON ReadableStream
 * and asserts the hook walks through the phase / outline / done states.
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCourseGeneration } from './useCourseGeneration'
import { useCourseStore } from '@/stores/courseStore'

vi.mock('@/services/courseApi', () => ({
  courseApi: {
    get: vi.fn(async (id: string) => ({
      id,
      user_id: 'u',
      project_id: 'p',
      title: 't',
      status: 'complete',
      input: {
        topic: 't',
        current_expertise: 'novice',
        target_expertise: 'competent',
        age_category: 'elementary',
        hours_min: 1,
        hours_max: 2,
        included_resources: [],
      },
      outline: null,
      validation_errors: null,
      model_used: 'm',
      created_at: '',
      updated_at: '',
      generated_at: null,
    })),
  },
}))

const enc = new TextEncoder()

function streamFromFrames(frames: object[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(enc.encode(JSON.stringify(frame) + '\n'))
      }
      controller.close()
    },
  })
}

function mockFetchOnce(body: ReadableStream<Uint8Array>, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(body, {
        status,
        headers: { 'content-type': 'application/x-ndjson' },
      })
    )
  )
}

const sampleOutline = {
  title: 'X',
  summary: 'Y',
  target_audience: 'Z',
  total_hours: 2,
  course_outcomes: [
    { id: 'out-c-1', text: 'a', bloom_level: 'understand' },
  ],
  modules: [
    {
      id: 'mod-1',
      title: 'M1',
      summary: 's',
      estimated_hours: 2,
      outcomes: [{ id: 'out-m-1-1', text: 'a', bloom_level: 'remember' }],
      lessons: [
        {
          id: 'les-1-1',
          title: 'L1',
          summary: 's',
          estimated_hours: 2,
          objectives: [
            { id: 'obj-1-1-1', text: 'do x', bloom_level: 'apply' },
          ],
          prerequisite_ids: [],
          readings: [],
          assessments: [],
        },
      ],
    },
  ],
}

describe('useCourseGeneration', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    useCourseStore.setState({
      courses: [],
      coursesById: {},
      loading: false,
      loaded: true,
      error: null,
    })
  })

  it('walks phase → outline → done', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'phase', name: 'research' },
        { type: 'chunk', content: 'notes ' },
        { type: 'chunk', content: 'more' },
        { type: 'tool_call', id: 't1', name: 'search_wikipedia', input: { query: 'x' } },
        { type: 'tool_result', id: 't1', ok: true, summary: '3 results' },
        { type: 'phase', name: 'assembling' },
        { type: 'outline', content: sampleOutline },
        { type: 'done', status: 'complete' },
      ])
    )

    const { result } = renderHook(() => useCourseGeneration())

    await act(async () => {
      await result.current.start('course-id')
    })

    await waitFor(() => {
      expect(result.current.phase).toBe('done')
    })
    expect(result.current.finalStatus).toBe('complete')
    expect(result.current.researchChunks).toBe('notes more')
    expect(result.current.toolCalls).toHaveLength(1)
    expect(result.current.toolCalls[0].status).toBe('ok')
    expect(result.current.outline?.title).toBe('X')
    expect(result.current.error).toBeNull()
    expect(result.current.isStreaming).toBe(false)
  })

  it('captures validation frames', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'phase', name: 'research' },
        { type: 'phase', name: 'assembling' },
        { type: 'outline', content: sampleOutline },
        {
          type: 'validation',
          errors: [{ path: 'modules[0].lessons[0]', msg: 'broken' }],
        },
        { type: 'done', status: 'needs_review' },
      ])
    )

    const { result } = renderHook(() => useCourseGeneration())
    await act(async () => {
      await result.current.start('course-id')
    })

    await waitFor(() => {
      expect(result.current.phase).toBe('done')
    })
    expect(result.current.finalStatus).toBe('needs_review')
    expect(result.current.validationErrors).toHaveLength(1)
    expect(result.current.validationErrors?.[0].msg).toBe('broken')
  })

  it('surfaces error frames', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'phase', name: 'research' },
        { type: 'error', message: 'RAG down' },
        { type: 'done', status: 'failed' },
      ])
    )

    const { result } = renderHook(() => useCourseGeneration())
    await act(async () => {
      await result.current.start('course-id')
    })

    await waitFor(() => {
      expect(result.current.phase).toBe('done')
    })
    expect(result.current.error).toBe('RAG down')
    expect(result.current.finalStatus).toBe('failed')
  })

  it('reset() clears state', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'phase', name: 'research' },
        { type: 'chunk', content: 'hi' },
        { type: 'done', status: 'complete' },
      ])
    )
    const { result } = renderHook(() => useCourseGeneration())
    await act(async () => {
      await result.current.start('course-id')
    })
    await waitFor(() => expect(result.current.phase).toBe('done'))

    act(() => result.current.reset())
    expect(result.current.phase).toBe('idle')
    expect(result.current.researchChunks).toBe('')
    expect(result.current.outline).toBeNull()
  })
})
