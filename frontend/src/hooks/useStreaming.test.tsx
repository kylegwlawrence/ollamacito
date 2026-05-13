/**
 * Tests for the Phase 4 useStreaming hook (POST + fetch ReadableStream + NDJSON).
 *
 * We stub `globalThis.fetch` to return a Response whose body is a
 * ReadableStream of UTF-8 bytes; that exercises the actual NDJSON parsing
 * in streamApi.ts without needing MSW.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useStreaming } from './useStreaming'

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
  })

  it('accumulates chunk content and calls onComplete with the full response', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'Hello ' },
        { type: 'chunk', content: 'world' },
        { type: 'done', truncated: false },
      ])
    )

    const onComplete = vi.fn()
    const { result } = renderHook(() => useStreaming(onComplete))

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(onComplete).toHaveBeenCalledTimes(1)
    expect(onComplete).toHaveBeenCalledWith('Hello world', false)
    expect(result.current.error).toBeNull()
    expect(result.current.isStreaming).toBe(false)
  })

  it('surfaces an error frame as an error and does NOT call onComplete', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'partial' },
        { type: 'error', message: 'boom' },
      ])
    )

    const onComplete = vi.fn()
    const { result } = renderHook(() => useStreaming(onComplete))

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(result.current.error).toBe('boom')
    expect(onComplete).not.toHaveBeenCalled()
  })

  it('passes the truncated flag through onComplete', async () => {
    mockFetchOnce(
      streamFromFrames([
        { type: 'chunk', content: 'half' },
        { type: 'done', truncated: true },
      ])
    )

    const onComplete = vi.fn()
    const { result } = renderHook(() => useStreaming(onComplete))

    await act(async () => {
      await result.current.sendMessage('chat-1', 'hi')
    })

    expect(onComplete).toHaveBeenCalledWith('half', true)
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
})
