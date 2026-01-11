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
    >
      <span className="project-item__icon">📁</span>
      <span className="project-item__name">{project.name}</span>
      {project.chat_count > 0 && (
        <span className="project-item__badge">{project.chat_count}</span>
      )}
      <button
        className="project-item__delete"
        onClick={handleDelete}
        title="Delete project"
        aria-label="Delete project"
      >
        ×
      </button>
    </div>
  )
}
