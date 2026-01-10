import { useState, useCallback, useRef } from 'react'
import { messageApi } from '@/services/messageApi'
import type { StreamChunk, StreamError } from '@/types'

interface UseStreamingReturn {
  sendMessage: (chatId: string, message: string) => Promise<void>
  isStreaming: boolean
  streamingContent: string
  error: string | null
  cancelStream: () => void
}

export const useStreaming = (
  onComplete?: (fullResponse: string) => void
): UseStreamingReturn => {
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const cancelStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
      setIsStreaming(false)
    }
  }, [])

  const sendMessage = useCallback(
    async (chatId: string, message: string) => {
      try {
        setIsStreaming(true)
        setStreamingContent('')
        setError(null)

        const streamUrl = messageApi.getStreamUrl(chatId, message)
        const eventSource = new EventSource(streamUrl)
        eventSourceRef.current = eventSource

        let fullResponse = ''

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as StreamChunk | StreamError

            if ('error' in data) {
              setError(data.error)
              eventSource.close()
              setIsStreaming(false)
              return
            }

            if (data.done) {
              eventSource.close()
              setIsStreaming(false)
              setStreamingContent('')
              if (onComplete) {
                onComplete(fullResponse)
              }
            } else {
              fullResponse += data.content
              setStreamingContent(fullResponse)
            }
          } catch (err) {
            console.error('Error parsing stream data:', err)
          }
        }

        eventSource.onerror = () => {
          eventSource.close()
          setIsStreaming(false)
          if (!fullResponse) {
            setError('Connection to server lost')
          } else {
            // Stream completed with error, but we have content
            setStreamingContent('')
            if (onComplete) {
              onComplete(fullResponse)
            }
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
        setIsStreaming(false)
      }
    },
    [onComplete]
  )

  return {
    sendMessage,
    isStreaming,
    streamingContent,
    error,
    cancelStream,
  }
}
