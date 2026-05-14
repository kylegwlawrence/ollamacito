import { useEffect, useRef, useState } from 'react'
import { usePromptStore } from '@/stores/promptStore'
import './PromptDialog.css'

/**
 * Modal text-input dialog driven by `usePromptStore.ask(...)`. Mount once
 * (in RootLayout). Shares modal styling with `ConfirmDialog`.
 */
export const PromptDialog = () => {
  const open = usePromptStore((s) => s.open)
  const title = usePromptStore((s) => s.title)
  const message = usePromptStore((s) => s.message)
  const placeholder = usePromptStore((s) => s.placeholder)
  const initialValue = usePromptStore((s) => s.initialValue)
  const confirmLabel = usePromptStore((s) => s.confirmLabel)
  const cancelLabel = usePromptStore((s) => s.cancelLabel)
  const resolveWith = usePromptStore((s) => s.resolveWith)

  const inputRef = useRef<HTMLInputElement>(null)
  const [value, setValue] = useState('')

  // Reset value when the dialog opens
  useEffect(() => {
    if (open) {
      setValue(initialValue ?? '')
      // Focus and select-all on next paint so the input is ready for typing
      const t = setTimeout(() => {
        inputRef.current?.focus()
        inputRef.current?.select()
      }, 0)
      return () => clearTimeout(t)
    }
  }, [open, initialValue])

  // Global Escape — close. Enter is handled at the input level so we don't
  // double-submit when focus is elsewhere.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        resolveWith(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, resolveWith])

  if (!open) return null

  const submit = () => {
    const trimmed = value.trim()
    resolveWith(trimmed ? trimmed : null)
  }

  return (
    <div
      className="prompt-dialog__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prompt-dialog-title"
      onClick={() => resolveWith(null)}
    >
      <div className="prompt-dialog" onClick={(e) => e.stopPropagation()}>
        <h2 id="prompt-dialog-title" className="prompt-dialog__title">
          {title}
        </h2>
        {message && <p className="prompt-dialog__message">{message}</p>}
        <input
          ref={inputRef}
          type="text"
          className="prompt-dialog__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submit()
            }
          }}
          aria-label={title}
        />
        <div className="prompt-dialog__actions">
          <button
            type="button"
            className="prompt-dialog__button prompt-dialog__button--secondary"
            onClick={() => resolveWith(null)}
          >
            {cancelLabel ?? 'Cancel'}
          </button>
          <button
            type="button"
            className="prompt-dialog__button prompt-dialog__button--default"
            onClick={submit}
            disabled={!value.trim()}
          >
            {confirmLabel ?? 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}
