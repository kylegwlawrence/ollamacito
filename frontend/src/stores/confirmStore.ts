/**
 * In-app confirmation dialog store.
 *
 * Replaces `window.confirm()` calls, which the browser permanently
 * suppresses for the session once the user clicks "Prevent this page from
 * creating additional dialogs". Once that's been triggered (very easy to do
 * by accident), every subsequent `window.confirm` returns false silently —
 * making every Delete button look broken.
 *
 * Use from any callsite:
 *
 *   const ok = await useConfirmStore.getState().ask({
 *     title: 'Delete this chat?',
 *     message: 'This cannot be undone.',
 *     confirmLabel: 'Delete',
 *     variant: 'danger',
 *   })
 *   if (!ok) return
 */
import { create } from 'zustand'

export type ConfirmVariant = 'danger' | 'default'

export interface ConfirmOptions {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: ConfirmVariant
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolve: ((ok: boolean) => void) | null
}

interface ConfirmStore extends ConfirmState {
  ask: (opts: ConfirmOptions) => Promise<boolean>
  /** Resolve with the given answer and close the dialog. */
  resolveWith: (ok: boolean) => void
}

const INITIAL: ConfirmState = {
  open: false,
  resolve: null,
  title: '',
  message: undefined,
  confirmLabel: undefined,
  cancelLabel: undefined,
  variant: 'default',
}

export const useConfirmStore = create<ConfirmStore>((set, get) => ({
  ...INITIAL,

  ask: (opts) =>
    new Promise<boolean>((resolve) => {
      // If a previous dialog is somehow still open, resolve it as cancelled
      // before opening the new one (defensive — shouldn't happen in practice).
      const prev = get().resolve
      if (prev) prev(false)

      set({
        open: true,
        resolve,
        title: opts.title,
        message: opts.message,
        confirmLabel: opts.confirmLabel,
        cancelLabel: opts.cancelLabel,
        variant: opts.variant ?? 'default',
      })
    }),

  resolveWith: (ok) => {
    const { resolve } = get()
    if (resolve) resolve(ok)
    set({ ...INITIAL })
  },
}))
