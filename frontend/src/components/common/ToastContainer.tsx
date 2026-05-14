import { useToastStore } from '@/stores/toastStore'
import { Icon } from './Icon'
import './ToastContainer.css'

const toastIcon: Record<string, string> = {
  success: 'check_circle',
  error: 'error',
  warning: 'warning',
  info: 'info',
}

export const ToastContainer = () => {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)

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
          <Icon name={toastIcon[toast.type] ?? 'info'} size={18} className="toast__icon" />
          <div className="toast__message">{toast.message}</div>
          <button
            className="toast__close"
            onClick={(e) => {
              e.stopPropagation()
              removeToast(toast.id)
            }}
            aria-label="Close notification"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}
