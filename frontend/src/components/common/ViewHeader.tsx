import { ReactNode } from 'react'
import './ViewHeader.css'

interface ViewHeaderProps {
  breadcrumb?: ReactNode
  leading?: ReactNode
  title: ReactNode
  actions?: ReactNode
}

export const ViewHeader = ({ breadcrumb, leading, title, actions }: ViewHeaderProps) => {
  return (
    <header className="view-header">
      {leading && <div className="view-header__leading">{leading}</div>}
      <div className="view-header__left">
        {breadcrumb && <div className="view-header__breadcrumb">{breadcrumb}</div>}
        <div className="view-header__title">{title}</div>
      </div>
      {actions && <div className="view-header__actions">{actions}</div>}
    </header>
  )
}
