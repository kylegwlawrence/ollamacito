# Critical Files
Backend
backend/app/db/models/chat.py - Add project_id foreign key
backend/app/db/models/project.py - New Project and ProjectFile models (create)
backend/app/schemas/project.py - Project Pydantic schemas (create)
backend/app/api/v1/endpoints/projects.py - Projects API endpoints (create)
backend/app/api/v1/endpoints/chats.py - Update to support project_id
backend/app/api/v1/endpoints/messages.py - Inject project context into system prompts
backend/app/utils/file_utils.py - File storage utilities (create)
backend/app/api/deps.py - Add get_project_or_404
backend/app/api/v1/router.py - Include projects router
Frontend
frontend/src/App.tsx - Add ViewProvider, ProjectProvider, use MainContent
frontend/src/components/MainContent.tsx - View router (create)
frontend/src/components/sidebar/Sidebar.tsx - Add Projects section
frontend/src/components/sidebar/ProjectItem.tsx - Project list item (create)
frontend/src/components/projects/ProjectDetail.tsx - Main project page (create)
frontend/src/components/projects/ProjectSettings.tsx - Settings page (create)
frontend/src/components/projects/FileUpload.tsx - File upload component (create)
frontend/src/components/projects/FileList.tsx - File list component (create)
frontend/src/contexts/ViewContext.tsx - Navigation context (create)
frontend/src/contexts/ProjectContext.tsx - Project state (create)
frontend/src/hooks/useProjects.ts - Project operations hook (create)
frontend/src/services/projectApi.ts - Project API client (create)
frontend/src/types/project.ts - Project TypeScript types (create)

# Key Design Decisions
1. Navigation Pattern
Context-based view switching instead of React Router

Maintains existing architecture pattern
ViewContext manages viewType and currentProjectId
MainContent component conditionally renders views
Trade-off: No URL routing, no shareable links (acceptable for desktop app)
2. File Storage
Filesystem storage instead of database BLOBs

Files saved to /backend/storage/projects/{project_id}/
Metadata in project_files table
UUID-based filenames prevent conflicts
10MB max file size enforced
Only .txt and .md initially
3. System Prompt Injection
Prepend project context to Ollama messages

Order: Project instructions → File contents → Chat system prompt
Format:

Project Context:
[custom_instructions]

Reference Files:
--- filename.txt ---
[content]
Automatically included for all project chats
No manual copy-paste needed
4. Chat-Project Relationship
Optional foreign key with CASCADE delete

project_id nullable (NULL = standalone chat)
Deleting project deletes chats (requires confirmation)
Cannot move chats between projects (future enhancement)
5. Memory Generation
Placeholder only in this phase

Disabled button with "Coming soon" tooltip
Reserves UI space
Actual implementation deferred to future phase
Verification Steps
After implementation, verify:

Database

Run migration successfully
Create project, verify in database
Create project chat, verify project_id foreign key
Delete project, verify cascade delete
File Upload

Upload .txt file → verify saved to disk and database
Upload .md file → verify success
Upload .pdf file → verify rejection
Upload 11MB file → verify rejection
Delete file → verify removed from disk and database
System Prompt

Create project with instructions
Upload reference file
Create chat in project
Send message
Verify AI response uses project context (ask it about the reference file)
Standalone Chats

Create chat from main sidebar
Verify project_id is null
Verify no project context in responses
UI Navigation

Click "Create Project" → enter name → navigates to project detail
Click project in sidebar → navigates to project detail
Click "Settings" → navigates to project settings
Click chat → navigates to chat view
Verify sidebar always visible
Edge Cases

Delete project with 10 chats → verify all chats deleted
Create project with empty instructions → verify allowed
Upload file with same name twice → verify no conflict (UUID filenames)
Switch rapidly between views → verify no race conditions
Success Criteria
✅ Users can create projects and give them names
✅ Users can add custom instructions to projects
✅ Users can upload .txt and .md files to projects
✅ Users can create chats within projects
✅ Project chats automatically include project context (instructions + files)
✅ Users can create standalone chats separate from projects
✅ Sidebar shows both Projects section and Chats section
✅ Clicking project navigates to project detail page
✅ Project detail page shows chats and files
✅ Users can edit project settings
✅ Deleting project deletes associated chats and files
✅ Database schema updated with proper relationships
✅ Backend API endpoints functional and tested
✅ Frontend UI matches design requirements
Stayed in plan mode
I understand! You want me to implement Phase 4 (Frontend Foundation) of the plan, and note that Phase 1 (Backend Database & Core API) has already been completed (skipping Alembic since this project uses init_db.py). Let me proceed with implementing Phase 4.