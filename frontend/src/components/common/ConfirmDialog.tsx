import { useEffect, useRef } from 'react'
import { useConfirmStore } from '@/stores/confirmStore'
import './ConfirmDialog.css'

/**
 * Modal confirm dialog driven by `useConfirmStore.ask(...)`. Mount once
 * (in RootLayout). The store-promise pattern means callsites get the same
 * imperative ergonomics as `window.confirm` but without the browser-suppression
 * footgun.
 */
export const ConfirmDialog = () => {
  const open = useConfirmStore((s) => s.open)
  const title = useConfirmStore((s) => s.title)
  const message = useConfirmStore((s) => s.message)
  const confirmLabel = useConfirmStore((s) => s.confirmLabel)
  const cancelLabel = useConfirmStore((s) => s.cancelLabel)
  const variant = useConfirmStore((s) => s.variant)
  const resolveWith = useConfirmStore((s) => s.resolveWith)
  const confirmRef = useRef<HTMLButtonElement>(null)

  // Focus the confirm button on open and wire keyboard shortcuts.
  useEffect(() => {
    if (!open) return
    confirmRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        resolveWith(false)
      } else if (e.key === 'Enter') {
        e.preventDefault()
        resolveWith(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, resolveWith])

  if (!open) return null

  return (
    <div
      className="confirm-dialog__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      onClick={() => resolveWith(false)}
    >
      <div
        className="confirm-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="confirm-dialog__title">
          {title}
        </h2>
        {message && <p className="confirm-dialog__message">{message}</p>}
        <div className="confirm-dialog__actions">
          <button
            type="button"
            className="confirm-dialog__button confirm-dialog__button--secondary"
            onClick={() => resolveWith(false)}
          >
            {cancelLabel ?? 'Cancel'}
          </button>
          <button
            type="button"
            ref={confirmRef}
            className={`confirm-dialog__button confirm-dialog__button--${variant ?? 'default'}`}
            onClick={() => resolveWith(true)}
          >
            {confirmLabel ?? 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}
