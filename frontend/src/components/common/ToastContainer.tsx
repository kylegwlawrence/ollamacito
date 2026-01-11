import { useToast } from '@/contexts/ToastContext'
import './ToastContainer.css'

export const ToastContainer = () => {
  const { toasts, removeToast } = useToast()

  return (
    <div className="toast-container" aria-live="polite" aria-atomic="false">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast--${toast.type}`}
          role="alert"
          aria-live="assertive"
          onClick={() => removeToast(toast.id)}
        >
          <div className="toast__icon" aria-hidden="true">
            {toast.type === 'success' && '✓'}
            {toast.type === 'error' && '✕'}
            {toast.type === 'warning' && '⚠'}
            {toast.type === 'info' && 'ℹ'}
          </div>
          <div className="toast__message">{toast.message}</div>
          <button
            className="toast__close"
            onClick={(e) => {
              e.stopPropagation()
              removeToast(toast.id)
            }}
            aria-label="Close notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
