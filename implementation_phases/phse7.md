Phase 7: Project Settings
Components:

Create ProjectSettings.tsx

Form fields:
Project name (text input, required)
Custom instructions (textarea, optional, rows=10)
Actions:
Save button (calls updateProject())
Delete project button (with confirmation dialog)
Back button (navigates to project detail)
Load project data on mount
Show save success/error feedback
Create ProjectSettings.css

Form layout styling
Textarea styling
Button group styling
Testing:

Update project name
Update custom instructions
Save changes and verify persistence
Delete project (verify confirmation, cascade delete chats)
Navigate back to project detail