Phase 6: Project Detail View
Components:

Create ProjectDetail.tsx

Load project and chats on mount
Layout sections: header, chats list, files list, memory (placeholder)
Header: project name, settings button
Chats: "New Chat" button, list of ChatItems
Files: FileUpload component, FileList component
Memory: Disabled button with tooltip "Coming soon"
Create FileUpload.tsx

File input accepting .txt, .md
Show upload progress
Validate file type and size client-side
Call projectApi.uploadFile()
Show success/error messages
Create FileList.tsx

Props: files: ProjectFile[], onDelete
Display: filename, type badge, size, content preview (truncated)
Actions: delete button per file
Empty state: "No files uploaded yet"
Create CSS files:

ProjectDetail.css
FileUpload.css
FileList.css
Testing:

Navigate to project detail
Create chat from project (verify project_id set)
Upload files (valid and invalid)
Delete files
Navigate to settings
