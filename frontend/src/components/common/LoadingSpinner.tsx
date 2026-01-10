import './LoadingSpinner.css'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
}

export const LoadingSpinner = ({ size = 'md' }: LoadingSpinnerProps) => {
  return (
    <div className={`spinner spinner--${size}`} role="status" aria-label="Loading">
      <span className="visually-hidden">Loading...</span>
    </div>
  )
}
