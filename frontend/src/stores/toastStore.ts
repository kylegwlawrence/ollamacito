/**
 * Toast notifications store (PLAN_NEW.md Phase 5).
 *
 * Replaces ToastContext. Callers use `useToastStore.getState().showToast(...)`
 * or, in components, `useToastStore((s) => s.showToast)`. The auto-dismiss
 * timer is started inside the action; no provider required.
 */
import { create } from 'zustand'
import type { Toast, ToastType } from '@/types/toast'

interface ToastStore {
  toasts: Toast[]
  showToast: (message: string, type?: ToastType, duration?: number) => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastStore>((set, get) => ({
  toasts: [],
  showToast: (message, type = 'info', duration = 4000) => {
    const id = `toast-${Date.now()}-${Math.random()}`
    const toast: Toast = { id, message, type, duration }
    set((s) => ({ toasts: [...s.toasts, toast] }))
    if (duration > 0) {
      setTimeout(() => get().removeToast(id), duration)
    }
  },
  removeToast: (id) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
  },
}))
