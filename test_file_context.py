#!/usr/bin/env python3
"""
Test script to verify project files are being loaded correctly.
Run this from the project root directory.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

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
            return

        # Display file details
        for i, file in enumerate(files, 1):
            content_length = len(file.content) if file.content else 0
            print(f"File {i}: {file.filename}")
            print(f"  - Type: {file.file_type}")
            print(f"  - Size: {file.file_size} bytes")
            print(f"  - Content loaded: {'Yes' if file.content else 'No'}")
            print(f"  - Content length: {content_length} chars")
            if file.content:
                preview = file.content[:100].replace('\n', '\\n')
                print(f"  - Preview: {preview}...")
            print()

        # Simulate message building
        print("=" * 60)
        print("SIMULATED MESSAGE TO OLLAMA:")
        print("=" * 60)

        message = "What can you tell me about these files?"
        file_context_parts = []

        for file in files:
            file_content = file.content if file.content else ""
            file_context_parts.append(f"[File: {file.filename}]\n{file_content}\n[End of File]")

        files_context = "\n\n".join(file_context_parts)
        message_content = f"{files_context}\n\n[User Message]\n{message}"

        print(f"Total message length: {len(message_content)} characters")
        print()
        print("First 500 characters:")
        print("-" * 60)
        print(message_content[:500])
        print("-" * 60)


if __name__ == "__main__":
    print("Testing Project File Context Loading")
    print("=" * 60)
    print()
    asyncio.run(test_file_loading())
