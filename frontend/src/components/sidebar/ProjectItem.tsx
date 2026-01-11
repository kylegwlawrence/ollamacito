import type { ProjectResponse } from '@/types'
import './ProjectItem.css'

interface ProjectItemProps {
  project: ProjectResponse
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
}

export const ProjectItem = ({ project, isActive, onSelect, onDelete }: ProjectItemProps) => {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete()
  }

  return (
    <div
      className={`project-item ${isActive ? 'project-item--active' : ''}`}
      onClick={onSelect}
      role="listitem"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect()
        }
      }}
      aria-label={`Project: ${project.name}, ${project.chat_count} chats`}
      aria-current={isActive ? 'page' : undefined}
    >
      <span className="project-item__icon" aria-hidden="true">📁</span>
      <span className="project-item__name">{project.name}</span>
      {project.chat_count > 0 && (
        <span className="project-item__badge" aria-label={`${project.chat_count} chats`}>
          {project.chat_count}
        </span>
      )}
      <button
        className="project-item__delete"
        onClick={handleDelete}
        title="Delete project"
        aria-label={`Delete project ${project.name}`}
      >
        ×
      </button>
    </div>
  )
}
