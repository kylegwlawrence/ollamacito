import './Icon.css'

interface IconProps {
  name: string
  size?: 16 | 18 | 20 | 24
  filled?: boolean
  title?: string
  className?: string
}

export const Icon = ({ name, size = 20, filled = false, title, className = '' }: IconProps) => {
  const hidden = !title
  return (
    <span
      className={`material-symbols-outlined icon ${className}`}
      style={{
        fontSize: `${size}px`,
        fontVariationSettings: `'FILL' ${filled ? 1 : 0}, 'wght' 400, 'GRAD' 0, 'opsz' ${size}`,
      }}
      aria-hidden={hidden || undefined}
      aria-label={title}
      role={title ? 'img' : undefined}
    >
      {name}
    </span>
  )
}
