/**
 * In-app text-prompt dialog store.
 *
 * Replaces `window.prompt()` calls, which modern browsers may suppress
 * silently (especially after a user dismisses one) — making "create project"
 * style flows look broken with no console output.
 *
 * Resolves with the trimmed string the user entered, or `null` if they
 * cancelled / submitted an empty value.
 *
 *   const name = await usePromptStore.getState().ask({
 *     title: 'Create new project',
 *     placeholder: 'Project name',
 *     confirmLabel: 'Create',
 *   })
 *   if (!name) return
 */
import { create } from 'zustand'

export interface PromptOptions {
  title: string
  message?: string
  placeholder?: string
  initialValue?: string
  confirmLabel?: string
  cancelLabel?: string
}

interface PromptState extends PromptOptions {
  open: boolean
  resolve: ((value: string | null) => void) | null
}

interface PromptStore extends PromptState {
  ask: (opts: PromptOptions) => Promise<string | null>
  resolveWith: (value: string | null) => void
}

const INITIAL: PromptState = {
  open: false,
  resolve: null,
  title: '',
  message: undefined,
  placeholder: undefined,
  initialValue: undefined,
  confirmLabel: undefined,
  cancelLabel: undefined,
}

export const usePromptStore = create<PromptStore>((set, get) => ({
  ...INITIAL,

  ask: (opts) =>
    new Promise<string | null>((resolve) => {
      const prev = get().resolve
      if (prev) prev(null)

      set({
        open: true,
        resolve,
        title: opts.title,
        message: opts.message,
        placeholder: opts.placeholder,
        initialValue: opts.initialValue,
        confirmLabel: opts.confirmLabel,
        cancelLabel: opts.cancelLabel,
      })
    }),

  resolveWith: (value) => {
    const { resolve } = get()
    if (resolve) resolve(value)
    set({ ...INITIAL })
  },
}))
