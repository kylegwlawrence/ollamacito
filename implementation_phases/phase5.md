# Phase 5: Sidebar Integration
## Components:

1. Create ProjectItem.tsx

    - Follow pattern from ChatItem.tsx - similar structure and behavior
    - prop interface:
    ```
    interface ProjectItemProps {
    project: ProjectResponse
    isActive: boolean
    onSelect: () => void
    onDelete: () => void
    }
    ```

    - Display elements:
        - Folder icon (📁) or use SVG similar to chat icons
        - Project name (truncate with ellipsis if too long)
        - Chat count badge (if count > 0)
        - Delete button (trash icon, shows on hover)
    - Click handlers:
        - Click project name → onSelect()
        - Click delete button → onDelete() with confirmation
    - Styling classes: .project-item, .project-item--active, .project-item__name, .project-item__badge
    - Import companion CSS file: ./ProjectItem.css

2. Modify Sidebar.tsx

- Add imports: useProjects, useView, ProjectItem
- Add state: const [projectsExpanded, setProjectsExpanded] = useState(true)
- Get projects data: const { projects, loading: projectsLoading, createProject, deleteProject } = useProjects()
- Get navigation: const { viewType, currentProjectId, navigateToProject } = useView()
- Add handleCreateProject():

```
const handleCreateProject = async () => {
  const name = window.prompt('Enter project name:')
  if (!name?.trim()) return

  try {
    const newProject = await createProject(name.trim())
    navigateToProject(newProject.id)
  } catch (err) {
    console.error('Failed to create project:', err)
    alert('Failed to create project')
  }
}
```
- Add handleDeleteProject(id):

```
const handleDeleteProject = async (projectId: string, chatCount: number) => {
  const msg = chatCount > 0
    ? `Delete this project and its ${chatCount} chat(s)?`
    : 'Delete this project?'

  if (!window.confirm(msg)) return

  try {
    await deleteProject(projectId)
    if (currentProjectId === projectId) {
      navigateToChat() // Return to chat view
    }
  } catch (err) {
    console.error('Failed to delete project:', err)
    alert('Failed to delete project')
  }
}
```
- Filter chats: Update chats list to show only standalone chats:

``
// In useChats() hook or in the component
const standaloneChats = chats.filter(chat => !chat.project_id)
```
- Update JSX structure:

```<div className="sidebar">
  {/* Header remains same */}

  {/* NEW: Projects Section */}
  <div className="sidebar__section">
    <div
      className="sidebar__section-header"
      onClick={() => setProjectsExpanded(!projectsExpanded)}
    >
      <span>{projectsExpanded ? '▼' : '▶'} Projects</span>
    </div>

    {projectsExpanded && (
      <div className="sidebar__projects">
        <button
          className="sidebar__new-button"
          onClick={handleCreateProject}
        >
          + Create Project
        </button>

        {projectsLoading ? (
          <LoadingSpinner />
        ) : (
          projects.map(project => (
            <ProjectItem
              key={project.id}
              project={project}
              isActive={viewType === 'project-detail' && currentProjectId === project.id}
              onSelect={() => navigateToProject(project.id)}
              onDelete={() => handleDeleteProject(project.id, project.chat_count)}
            />
          ))
        )}
      </div>
    )}
  </div>

  {/* MODIFIED: Chats Section - now shows only standalone chats */}
  <div className="sidebar__section">
    <div className="sidebar__section-header">
      <span>Chats</span>
    </div>

    <div className="sidebar__chats">
      {/* Existing new chat button and ChatItem list */}
      {/* Filter chats to standaloneChats */}
      {standaloneChats.map(chat => (
        <ChatItem key={chat.id} ... />
      ))}
    </div>
  </div>
</div>
```

3. Create ProjectItem.css

- Follow styling patterns from ChatItem.css
- Use CSS variables from theme
- Example structure:
```
.project-item {
  display: flex;
  align-items: center;
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background-color var(--transition-fast);
  gap: 0.75rem;
}

.project-item:hover {
  background-color: var(--bg-tertiary);
}

.project-item--active {
  background-color: var(--accent-color);
  color: var(--bg-primary);
}

.project-item__icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.project-item__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-item__badge {
  background-color: var(--accent-color);
  color: var(--bg-primary);
  padding: 0.125rem 0.5rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.project-item__delete {
  opacity: 0;
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0.25rem;
  transition: opacity var(--transition-fast);
}

.project-item:hover .project-item__delete {
  opacity: 1;
}

.project-item__delete:hover {
  color: var(--error-color);
}```
4. Update Sidebar.css

- Add section styling:

.sidebar__section {
  margin-bottom: 1.5rem;
}

.sidebar__section-header {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar__section-header:hover {
  color: var(--text-primary);
}

.sidebar__projects,
.sidebar__chats {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sidebar__new-button {
  margin: 0.5rem 1rem;
  padding: 0.75rem;
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.sidebar__new-button:hover {
  background-color: var(--accent-color);
  color: var(--bg-primary);
  border-color: var(--accent-color);
}
```
## Testing:

- Navigate to http://localhost:5173
- Verify "Projects" section appears above "Chats" section
- Click "+ Create Project" button
    - Enter project name in prompt
    - Verify project appears in list
    - Verify navigation to project detail view (placeholder)
- Click project in list
    - Verify project-item gets --active class
    - Verify navigates to project detail
- Hover over project item
    - Verify delete button appears
- Click delete button
    - Verify confirmation dialog appears
    - Verify project is removed from list
    - If active project deleted, verify returns to chat view
- Click collapse arrow on "Projects" header
    - Verify projects list collapses
    - Click again to expand
Create a chat (should be standalone)
    - Verify chat appears in "Chats" section, not in any project
    - Verify only standalone chats (project_id === null) appear in "Chats" section
