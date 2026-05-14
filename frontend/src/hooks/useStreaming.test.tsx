/**
 * Tests for the Phase 4 useStreaming hook + the streamingStore that backs
 * it. The store owns the in-flight fetch so navigation doesn't abort it
 * (see streamingStore.ts).
 *
 * We stub `globalThis.fetch` to return a Response whose body is a
 * ReadableStream of UTF-8 bytes; that exercises the actual NDJSON parsing
 * in streamApi.ts without needing MSW. `chatApi.get` is mocked because
 * the store refetches the chat on stream completion.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useStreaming } from './useStreaming'
import { useStreamingStore } from '@/stores/streamingStore'
import { useChatStore } from '@/stores/chatStore'

vi.mock('@/services/chatApi', () => ({
  chatApi: {
    get: vi.fn(async (id: string) => ({
      id,
      title: 'test',
      model: 'm',
      project_id: null,
      created_at: '',
      updated_at: '',
      messages: [],
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

describe('useStreaming', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    // Reset the singleton stores so tests don't leak state.
    useStreamingStore.setState({
      activeChatId: null,
      isStreaming: false,
      streamingContent: '',
      streamingToolCalls: [],
      error: null,
    })
    useChatStore.setState({ currentChat: null, messages: [], selectedFileIds: [] })
  })

  it('accumulates chunk content and ends with isStreaming=false', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'Hello ' },
        { type: 'chunk', content: 'world' },
        { type: 'done', truncated: false },
      ])
    )

    const { result } = renderHook(() => useStreaming())

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(result.current.error).toBeNull()
    expect(result.current.isStreaming).toBe(false)
    expect(result.current.streamingContent).toBe('')
  })

  it('surfaces an error frame as an error', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'partial' },
        { type: 'error', message: 'boom' },
      ])
    )

    const { result } = renderHook(() => useStreaming())

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(result.current.error).toBe('boom')
    expect(result.current.isStreaming).toBe(false)
  })

  it('handles truncated=true cleanly', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'half' },
        { type: 'done', truncated: true },
      ])
    )

    const { result } = renderHook(() => useStreaming())

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(result.current.error).toBeNull()
    expect(result.current.isStreaming).toBe(false)
  })

  it('rejects a second sendMessage while one is already streaming', async () => {
    // Build a stream that never closes on its own so the first call stays
    // in-flight until we explicitly close it.
    let close: (() => void) | undefined
    const slowBody = new ReadableStream<Uint8Array>({
      start(controller) {
        close = () => {
          controller.enqueue(
            enc.encode(JSON.stringify({ type: 'done', truncated: false }) + '\n')
          )
          controller.close()
        }
      },
    })
    mockFetchOnce(slowBody)

    const { result } = renderHook(() => useStreaming())

    let first: Promise<void>
    act(() => {
      first = result.current.sendMessage('chat-1', 'first')
    })

    // Wait for isStreaming to flip on, then fire the second call.
    await waitFor(() => expect(result.current.isStreaming).toBe(true))
    await act(async () => {
      await result.current.sendMessage('chat-1', 'second')
    })

    expect(result.current.error).toBe('A message is already streaming.')

    // Drain the slow stream
    close!()
    await act(async () => {
      await first!
    })
  })

  it('routes to the agent endpoint when agentMode=true', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'ok' },
        { type: 'done', truncated: false },
      ])
    )

    const { result } = renderHook(() => useStreaming())

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi', [], true)
    })

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls.length).toBe(1)
    const url = calls[0][0] as string
    expect(url).toContain('/chats/chat-1/agent')
    expect(url).not.toContain('/stream')
  })

  it('routes to the stream endpoint when agentMode is omitted', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'ok' },
        { type: 'done', truncated: false },
      ])
    )

    const { result } = renderHook(() => useStreaming())

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls.length).toBe(1)
    const url = calls[0][0] as string
    expect(url).toContain('/chats/chat-1/stream')
    expect(url).not.toContain('/agent')
  })

  it('accumulates tool_call and tool_result frames into streamingToolCalls', async () => {
    let close: (() => void) | undefined
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        // Emit a tool_call first so we can observe the pending state.
        controller.enqueue(
          enc.encode(
            JSON.stringify({
              type: 'tool_call',
              id: 'tc-1',
              name: 'search_wikipedia',
              input: { query: 'frogs' },
            }) + '\n'
          )
        )
        close = () => {
          controller.enqueue(
            enc.encode(
              JSON.stringify({
                type: 'tool_result',
                id: 'tc-1',
                ok: true,
                summary: '3 results',
              }) + '\n'
            )
          )
          controller.enqueue(
            enc.encode(
              JSON.stringify({ type: 'chunk', content: 'frogs are amphibians' }) + '\n'
            )
          )
          controller.enqueue(
            enc.encode(
              JSON.stringify({ type: 'done', truncated: false }) + '\n'
            )
          )
          controller.close()
        }
      },
    })
    mockFetchOnce(body)

    const { result } = renderHook(() => useStreaming())

    let pending: Promise<void>
    act(() => {
      pending = result.current.sendMessage('chat-1', 'tell me about frogs', [], true)
    })

    // The first frame (tool_call) should land while still streaming.
    await waitFor(() =>
      expect(result.current.streamingToolCalls.length).toBe(1)
    )
    expect(result.current.streamingToolCalls[0].name).toBe('search_wikipedia')
    expect(result.current.streamingToolCalls[0].ok).toBe(false) // pending

    // Drain: result + chunk + done.
    close!()
    await act(async () => {
      await pending!
    })

    // After completion the streaming bubble (and its tool calls) are cleared.
    expect(result.current.streamingToolCalls).toEqual([])
    expect(result.current.isStreaming).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('exposes activeChatId so consumers can scope the bubble to one chat', async () => {
    let close: (() => void) | undefined
    const slowBody = new ReadableStream<Uint8Array>({
      start(controller) {
        close = () => {
          controller.enqueue(
            enc.encode(JSON.stringify({ type: 'done', truncated: false }) + '\n')
          )
          controller.close()
        }
      },
    })
    mockFetchOnce(slowBody)

    const { result } = renderHook(() => useStreaming())

    let pending: Promise<void>
    act(() => {
      pending = result.current.sendMessage('chat-XYZ', 'hi')
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))
    expect(result.current.activeChatId).toBe('chat-XYZ')

    close!()
    await act(async () => {
      await pending!
    })
    expect(result.current.activeChatId).toBeNull()
  })
})
