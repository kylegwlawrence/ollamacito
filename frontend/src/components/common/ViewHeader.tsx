import { ReactNode } from 'react'
import './ViewHeader.css'

interface ViewHeaderProps {
  breadcrumb?: ReactNode
  title: ReactNode
  actions?: ReactNode
}

export const ViewHeader = ({ breadcrumb, title, actions }: ViewHeaderProps) => {
  return (
    <header className="view-header">
      <div className="view-header__left">
        {breadcrumb && <div className="view-header__breadcrumb">{breadcrumb}</div>}
        <div className="view-header__title">{title}</div>
      </div>
      {actions && <div className="view-header__actions">{actions}</div>}
    </header>
  )
}
