# Debugging File Context Feature

## Quick Test Steps

### 1. Test Database Content

Run the test script to verify files are in the database:

```bash
cd /Users/kylelawrence/Documents/PROJECTS/ollama_gui_app
python test_file_context.py
```

**Expected output:**
- Should show chat and project details
- Should list all files with their content
- Should show simulated message with file context

**If no files are found:**
- Upload files through the UI first
- Check that files have content (not empty)

### 2. Check Backend Logs

Start the backend with detailed logging and watch for these messages:

```bash
cd backend
# Start backend (your normal command)
```

**When you send a message, look for:**

```
INFO: Chat {chat_id} belongs to project {project_id}, loading project files
INFO: Loaded X files from database for project {project_id}
INFO: Auto-attaching X project file(s) to chat {chat_id}
INFO: Including file {filename} ({file_type}, X chars) as context for chat {chat_id}
INFO: Sending to Ollama - Chat {chat_id}, Message length: X chars, Number of messages in history: X
```

**If you see "No files found in project":**
- Files aren't associated with the project
- Check project_id matches

**If you see "Loaded 0 files":**
- Database query isn't finding files
- Run the test script to verify

### 3. Check Frontend Console

Open browser DevTools (F12) and check console when sending a message:

**Expected logs:**
```
[ChatContainer] Sending message: {chatId, projectId, hasProjectFiles, fileCount}
[MessageAPI] Stream URL: http://localhost:8000/api/v1/chats/{id}/stream?message=...
```

**Verify:**
- `projectId` is not null
- `hasProjectFiles` is true
- `fileCount` > 0

### 4. Test Message Flow

1. Create or open a project
2. Upload a test file (small text file)
3. Create a chat in that project
4. Send message: "What files do you have access to?"
5. AI should respond acknowledging the files

## Common Issues

### Issue: AI responds but doesn't mention files

**Cause:** Files aren't being included in message context

**Debug:**
1. Check backend logs for "Auto-attaching" messages
2. Run test script to verify files exist
3. Check message length in logs (should be much larger with files)

### Issue: "No files found in project" log

**Cause:** Chat's `project_id` doesn't match files' `project_id`

**Fix:**
1. Verify chat belongs to project (check `project_id` in chat record)
2. Verify files belong to same project
3. Check database relationships

### Issue: AI doesn't respond at all

**Cause:** Could be multiple issues

**Debug:**
1. Check if Ollama is running: `ollama list`
2. Check backend logs for errors
3. Check if stream is reaching Ollama
4. Verify message isn't too large (token limit)

### Issue: Files uploaded but have no content

**Cause:** File upload didn't save content to database

**Fix:**
1. Check file upload endpoint logs
2. Verify `content` field is being populated
3. Re-upload files

## Manual Database Check

If test script doesn't work, check database directly:

```sql
-- Check if files exist and have content
SELECT id, filename, file_type, LENGTH(content) as content_length
FROM project_files
WHERE project_id = 'YOUR_PROJECT_ID';

-- Check if chat belongs to project
SELECT id, title, project_id
FROM chats
WHERE project_id IS NOT NULL;
```

## Expected Behavior

When working correctly:

1. **Backend logs show:**
   - Files being loaded from database
   - Files being attached to message
   - Large message length (includes all file content)

2. **AI response mentions files:**
   - Acknowledges file names
   - Can answer questions about file content
   - Can summarize or analyze files

3. **Frontend shows:**
   - File count badge above message input
   - "X project file(s) available as context"

## Still Not Working?

Run test script and share output. Also share:
- Backend logs when sending message
- Frontend console logs
- Whether test script found files
- Database query results
