import { useCallback, useEffect, useRef } from 'react'

/**
 * Returns a stable wrapper that delays calls to `fn` by `delayMs` and
 * collapses bursts. The latest arguments win. The wrapper also exposes a
 * `flush()` method that runs any pending invocation immediately — handy on
 * blur to commit pending text-input edits before the user navigates away.
 *
 * Pending invocations are cancelled on unmount, so a save fired right before
 * unmount won't fire if it hasn't elapsed. Call flush() before navigating
 * if you need that guarantee.
 */
export interface DebouncedCallback<TArgs extends unknown[]> {
  (...args: TArgs): void
  flush: () => void
  cancel: () => void
}

export function useDebouncedCallback<TArgs extends unknown[]>(
  fn: (...args: TArgs) => void,
  delayMs: number,
): DebouncedCallback<TArgs> {
  const fnRef = useRef(fn)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingArgsRef = useRef<TArgs | null>(null)

  useEffect(() => {
    fnRef.current = fn
  }, [fn])

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [])

  const debounced = useCallback(
    (...args: TArgs) => {
      pendingArgsRef.current = args
      if (timerRef.current !== null) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        timerRef.current = null
        const pending = pendingArgsRef.current
        pendingArgsRef.current = null
        if (pending) fnRef.current(...pending)
      }, delayMs)
    },
    [delayMs],
  ) as DebouncedCallback<TArgs>

  debounced.flush = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const pending = pendingArgsRef.current
    pendingArgsRef.current = null
    if (pending) fnRef.current(...pending)
  }, [])

  debounced.cancel = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    pendingArgsRef.current = null
  }, [])

  return debounced
}
