import { describe, expect, it, beforeEach, vi } from 'vitest'
import { useToastStore } from './toastStore'

describe('toastStore', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] })
    vi.useFakeTimers()
  })

  it('shows a toast and auto-dismisses after duration', () => {
    useToastStore.getState().showToast('hi', 'info', 4000)
    expect(useToastStore.getState().toasts).toHaveLength(1)
    expect(useToastStore.getState().toasts[0].message).toBe('hi')

    vi.advanceTimersByTime(4001)

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('does not auto-dismiss when duration is 0', () => {
    useToastStore.getState().showToast('sticky', 'error', 0)
    vi.advanceTimersByTime(10_000)
    expect(useToastStore.getState().toasts).toHaveLength(1)
  })

  it('removeToast filters by id', () => {
    useToastStore.getState().showToast('a', 'info', 0)
    useToastStore.getState().showToast('b', 'info', 0)
    const [first, second] = useToastStore.getState().toasts
    useToastStore.getState().removeToast(first.id)
    expect(useToastStore.getState().toasts).toEqual([second])
  })
})
