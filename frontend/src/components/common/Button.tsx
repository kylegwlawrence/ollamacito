import { ButtonHTMLAttributes, ReactNode } from 'react'
import { Icon } from './Icon'
import './Button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  children?: ReactNode
  leadingIcon?: string
  trailingIcon?: string
  iconOnly?: boolean
}

export const Button = ({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  leadingIcon,
  trailingIcon,
  iconOnly = false,
  ...props
}: ButtonProps) => {
  const iconSize = size === 'sm' ? 16 : size === 'lg' ? 20 : 18

  return (
    <button
      className={`btn btn--${variant} btn--${size}${iconOnly ? ' btn--icon-only' : ''} ${className}`}
      {...props}
    >
      {leadingIcon && <Icon name={leadingIcon} size={iconSize} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={iconSize} />}
    </button>
  )
}
