#!/usr/bin/env python3
"""
Test script to verify project files are being loaded correctly.
Run this from the backend directory with: python test_file_context.py
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Chat, Project, ProjectFile


async def test_file_loading():
    """Test loading files for a project chat."""
    async with AsyncSessionLocal() as session:
        # Get first project chat
        query = select(Chat).where(Chat.project_id.isnot(None)).limit(1)
        result = await session.execute(query)
        chat = result.scalar_one_or_none()

        if not chat:
            print("❌ No project chats found in database")
            print("\nPlease:")
            print("1. Create a project")
            print("2. Upload some files to the project")
            print("3. Create a chat in that project")
            return

        print(f"✓ Found chat: {chat.id}")
        print(f"  - Title: {chat.title}")
        print(f"  - Project ID: {chat.project_id}")
        print(f"  - Model: {chat.model}")
        print()

        # Get project
        project_query = select(Project).where(Project.id == chat.project_id)
        result = await session.execute(project_query)
        project = result.scalar_one_or_none()

        if project:
            print(f"✓ Found project: {project.name}")
            if project.custom_instructions:
                print(f"  - Custom instructions: {project.custom_instructions[:100]}...")
            print()

        # Load files
        files_query = select(ProjectFile).where(
            ProjectFile.project_id == chat.project_id
        ).order_by(ProjectFile.created_at.asc())
        result = await session.execute(files_query)
        files = result.scalars().all()

        print(f"✓ Found {len(files)} file(s) in project")
        print()

        if not files:
            print("⚠️  No files in this project. Upload some files to test.")
            print("\nTo test the file context feature:")
            print("1. Go to the project page in the UI")
            print("2. Upload a text, JSON, CSV, or markdown file")
            print("3. Run this script again")
            return

        # Display file details
        for i, file in enumerate(files, 1):
            content_length = len(file.content) if file.content else 0
            has_content = "✓ Yes" if file.content else "✗ No"
            print(f"File {i}: {file.filename}")
            print(f"  - Type: {file.file_type}")
            print(f"  - Size: {file.file_size} bytes")
            print(f"  - Content in DB: {has_content}")
            print(f"  - Content length: {content_length} chars")
            if file.content:
                preview = file.content[:100].replace('\n', '\\n')
                print(f"  - Preview: {preview}...")
            else:
                print(f"  - ⚠️  WARNING: File has no content! Re-upload the file.")
            print()

        # Simulate message building
        print("=" * 60)
        print("SIMULATED MESSAGE TO OLLAMA:")
        print("=" * 60)

        message = "What can you tell me about these files?"
        file_context_parts = []
        total_file_chars = 0

        for file in files:
            file_content = file.content if file.content else ""
            total_file_chars += len(file_content)
            file_context_parts.append(f"[File: {file.filename}]\n{file_content}\n[End of File]")

        files_context = "\n\n".join(file_context_parts)
        message_content = f"{files_context}\n\n[User Message]\n{message}"

        print(f"Total message length: {len(message_content)} characters")
        print(f"  - Files context: {total_file_chars} chars")
        print(f"  - User message: {len(message)} chars")
        print()
        print("First 500 characters of what will be sent to Ollama:")
        print("-" * 60)
        print(message_content[:500])
        print("-" * 60)
        print()
        print("✓ Files are being loaded correctly!")
        print("\nIf the AI still doesn't respond with file context:")
        print("1. Check backend logs when sending a message")
        print("2. Look for 'Auto-attaching X project file(s)' message")
        print("3. Look for 'Total context size' message")
        print("4. Make sure Ollama is running: ollama list")


if __name__ == "__main__":
    print("Testing Project File Context Loading")
    print("=" * 60)
    print()
    asyncio.run(test_file_loading())
