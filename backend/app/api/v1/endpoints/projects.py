"""
API endpoints for project management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, get_project_or_404
from app.core.logging import get_logger
from app.db.models import Chat, Project, ProjectFile, User
from app.db.models import Settings as UserSettings
from app.schemas.chat import ChatListResponse, ChatResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectFileCreate,
    ProjectFileResponse,
    ProjectListResponse,
    ProjectMemoryGenerateResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithDetails,
    RagInfoRequest,
)
from app.services.ollama_service import ollama_service
from app.services.rag_service import rag_service

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_archived: bool = Query(False, description="Include archived projects"),
):
    """Get paginated list of projects for the current user."""
    try:
        # Build query
        query = select(Project).where(Project.user_id == current_user.id)
        if not include_archived:
            query = query.where(Project.is_archived == False)  # noqa: E712

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar() or 0

        # Get paginated results
        query = query.order_by(Project.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.options(selectinload(Project.chats), selectinload(Project.files))

        result = await db.execute(query)
        projects = result.scalars().all()

        # Add counts to each project
        project_responses = []
        for project in projects:
            project_dict = {
                "id": project.id,
                "name": project.name,
                "custom_instructions": project.custom_instructions,
                "default_model": project.default_model,
                "temperature": project.temperature,
                "max_tokens": project.max_tokens,
                "auto_attach_all_files": project.auto_attach_all_files,
                "memory": project.memory,
                "rag_enabled": project.rag_enabled,
                "rag_server_url": project.rag_server_url,
                "rag_corpus_id": project.rag_corpus_id,
                "rag_top_k": project.rag_top_k,
                "is_archived": project.is_archived,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "chat_count": len(project.chats),
                "file_count": len(project.files),
            }
            project_responses.append(ProjectResponse(**project_dict))

        total_pages = (total + page_size - 1) // page_size

        return ProjectListResponse(
            projects=project_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving projects",
        ) from e


@router.get("/{project_id}", response_model=ProjectWithDetails)
async def get_project(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific project with all details including files.

    Args:
        project: Project from dependency
        db: Database session

    Returns:
        ProjectWithDetails: Project with files
    """
    # Load files for the project
    query = (
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.files), selectinload(Project.chats))
    )
    result = await db.execute(query)
    project_with_details = result.scalar_one()

    # Sort files by created_at
    sorted_files = sorted(project_with_details.files, key=lambda f: f.created_at)

    return ProjectWithDetails(
        id=project_with_details.id,
        name=project_with_details.name,
        custom_instructions=project_with_details.custom_instructions,
        memory=project_with_details.memory,
        default_model=project_with_details.default_model,
        temperature=project_with_details.temperature,
        max_tokens=project_with_details.max_tokens,
        auto_attach_all_files=project_with_details.auto_attach_all_files,
        rag_enabled=project_with_details.rag_enabled,
        rag_server_url=project_with_details.rag_server_url,
        rag_corpus_id=project_with_details.rag_corpus_id,
        rag_top_k=project_with_details.rag_top_k,
        is_archived=project_with_details.is_archived,
        created_at=project_with_details.created_at,
        updated_at=project_with_details.updated_at,
        chat_count=len(project_with_details.chats),
        file_count=len(sorted_files),
        files=sorted_files,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new project owned by the current user."""
    try:
        new_project = Project(
            user_id=current_user.id,
            name=project_data.name,
            custom_instructions=project_data.custom_instructions,
            memory=project_data.memory,
            default_model=project_data.default_model,
            temperature=project_data.temperature,
            max_tokens=project_data.max_tokens,
            auto_attach_all_files=project_data.auto_attach_all_files,
            rag_enabled=project_data.rag_enabled,
            rag_server_url=project_data.rag_server_url,
            rag_corpus_id=project_data.rag_corpus_id,
            rag_top_k=project_data.rag_top_k,
        )
        db.add(new_project)
        await db.flush()
        await db.refresh(new_project)

        logger.info(f"Created project {new_project.id}")

        return ProjectResponse(
            id=new_project.id,
            name=new_project.name,
            custom_instructions=new_project.custom_instructions,
            memory=new_project.memory,
            default_model=new_project.default_model,
            temperature=new_project.temperature,
            max_tokens=new_project.max_tokens,
            auto_attach_all_files=new_project.auto_attach_all_files,
            rag_enabled=new_project.rag_enabled,
            rag_server_url=new_project.rag_server_url,
            rag_corpus_id=new_project.rag_corpus_id,
            rag_top_k=new_project.rag_top_k,
            is_archived=new_project.is_archived,
            created_at=new_project.created_at,
            updated_at=new_project.updated_at,
            chat_count=0,
            file_count=0,
        )

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating project",
        ) from e


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_data: ProjectUpdate,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a project.

    Args:
        project_data: Project update data
        project: Project from dependency
        db: Database session

    Returns:
        ProjectResponse: Updated project
    """
    # Update fields. For nullable string fields we use the request's `model_fields_set`
    # so the caller can explicitly clear (set to null) versus omit (leave unchanged).
    fields_set = project_data.model_fields_set

    if project_data.name is not None:
        project.name = project_data.name
    if "custom_instructions" in fields_set:
        project.custom_instructions = project_data.custom_instructions
    if "memory" in fields_set:
        project.memory = project_data.memory
    if project_data.is_archived is not None:
        project.is_archived = project_data.is_archived
    if project_data.default_model is not None:
        project.default_model = project_data.default_model
    if project_data.temperature is not None:
        project.temperature = project_data.temperature
    if project_data.max_tokens is not None:
        project.max_tokens = project_data.max_tokens
    if project_data.auto_attach_all_files is not None:
        project.auto_attach_all_files = project_data.auto_attach_all_files
    if project_data.rag_enabled is not None:
        project.rag_enabled = project_data.rag_enabled
    if "rag_server_url" in fields_set:
        project.rag_server_url = project_data.rag_server_url
    if "rag_corpus_id" in fields_set:
        project.rag_corpus_id = project_data.rag_corpus_id
    if "rag_top_k" in fields_set:
        project.rag_top_k = project_data.rag_top_k

    await db.flush()
    await db.refresh(project)

    logger.info(f"Updated project {project.id}")

    # Get counts
    chat_count_query = select(func.count()).where(Chat.project_id == project.id)
    result = await db.execute(chat_count_query)
    chat_count = result.scalar() or 0

    file_count_query = select(func.count()).where(ProjectFile.project_id == project.id)
    result = await db.execute(file_count_query)
    file_count = result.scalar() or 0

    return ProjectResponse(
        id=project.id,
        name=project.name,
        custom_instructions=project.custom_instructions,
        memory=project.memory,
        default_model=project.default_model,
        temperature=project.temperature,
        max_tokens=project.max_tokens,
        auto_attach_all_files=project.auto_attach_all_files,
        rag_enabled=project.rag_enabled,
        rag_server_url=project.rag_server_url,
        rag_corpus_id=project.rag_corpus_id,
        rag_top_k=project.rag_top_k,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chat_count=chat_count,
        file_count=file_count,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a project and all its chats and files.

    Args:
        project: Project from dependency
        db: Database session
    """
    project_id = project.id
    await db.delete(project)
    await db.flush()

    logger.info(f"Deleted project {project_id}")


@router.get("/{project_id}/chats", response_model=ChatListResponse)
async def get_project_chats(
    project_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all chats in a project (paginated).

    Args:
        project_id: Project UUID
        page: Page number
        page_size: Items per page
        project: Project from dependency
        db: Database session

    Returns:
        ChatListResponse: Paginated list of chats
    """
    try:
        # Build query
        query = select(Chat).where(Chat.project_id == project.id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar() or 0

        # Get paginated results
        query = query.order_by(Chat.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.options(selectinload(Chat.messages))

        result = await db.execute(query)
        chats = result.scalars().all()

        # Add message count to each chat
        chat_responses = []
        for chat in chats:
            chat_dict = {
                "id": chat.id,
                "title": chat.title,
                "model": chat.model,
                "is_archived": chat.is_archived,
                "project_id": chat.project_id,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "message_count": len(chat.messages),
            }
            chat_responses.append(ChatResponse(**chat_dict))

        total_pages = (total + page_size - 1) // page_size

        return ChatListResponse(
            chats=chat_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing project chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving project chats",
        ) from e


@router.post(
    "/{project_id}/files",
    response_model=ProjectFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file_data: ProjectFileCreate,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file to a project.

    Args:
        file_data: File upload data
        project: Project from dependency
        db: Database session

    Returns:
        ProjectFileResponse: Created file
    """
    try:
        # Generate content preview (first 200 chars)
        content_preview = (
            file_data.content[:200]
            if len(file_data.content) > 200
            else file_data.content
        )

        # Create file record
        new_file = ProjectFile(
            project_id=project.id,
            filename=file_data.filename,
            file_path=f"project_{project.id}/{file_data.filename}",  # Virtual path
            file_type=file_data.file_type,
            file_size=len(file_data.content),
            content_preview=content_preview,
            content=file_data.content,
        )
        db.add(new_file)
        await db.flush()
        await db.refresh(new_file)

        logger.info(f"Uploaded file {new_file.id} to project {project.id}")

        return ProjectFileResponse(
            id=new_file.id,
            project_id=new_file.project_id,
            filename=new_file.filename,
            file_type=new_file.file_type,
            file_size=new_file.file_size,
            content_preview=new_file.content_preview,
            content=new_file.content,
            created_at=new_file.created_at,
        )

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading file",
        ) from e


@router.get("/{project_id}/files/{file_id}", response_model=ProjectFileResponse)
async def get_file(
    file_id: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific file from a project.

    Args:
        file_id: File UUID
        project: Project from dependency
        db: Database session

    Returns:
        ProjectFileResponse: File details with content
    """
    try:
        # Query for the file
        query = select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project.id,
        )
        result = await db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        return ProjectFileResponse(
            id=file.id,
            project_id=file.project_id,
            filename=file.filename,
            file_type=file.file_type,
            file_size=file.file_size,
            content_preview=file.content_preview,
            content=file.content,
            created_at=file.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving file",
        ) from e


@router.post("/{project_id}/rag/info")
async def get_rag_info(
    body: RagInfoRequest,
    project: Project = Depends(get_project_or_404),
):
    """
    Proxy a GET /rag/info call to the supplied RAG server URL.

    Used by the "Test connection" button in project settings: the user types
    a URL, we call the server, and return its info payload so the UI can
    populate the corpus dropdown. The URL is taken from the request body
    (not from the project) so the user can validate before saving.

    Connection failures surface as 503 via the RagConnectionError handler.
    """
    info = await rag_service.get_info(body.rag_server_url)
    logger.info(
        f"Fetched RAG /info for project {project.id} from {body.rag_server_url}"
    )
    return info


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a file from a project.

    Args:
        file_id: File UUID
        project: Project from dependency
        db: Database session
    """
    try:
        # Query for the file
        query = select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project.id,
        )
        result = await db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        await db.delete(file)
        await db.flush()

        logger.info(f"Deleted file {file_id} from project {project.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting file",
        ) from e


@router.post(
    "/{project_id}/memory/generate",
    response_model=ProjectMemoryGenerateResponse,
)
async def generate_project_memory(
    project: Project = Depends(get_project_or_404),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemoryGenerateResponse:
    """
    Generate a project memory document from up to 20 most-recent chats.

    Does NOT persist — returns the text, lets the user edit, then they save
    via PATCH /projects/{id}. Cross-user projects yield 404 via the
    ownership dependency; projects with no chats yield 422.
    """
    chats = (
        (
            await db.execute(
                select(Chat)
                .where(Chat.project_id == project.id)
                .order_by(Chat.created_at.desc())
                .limit(20)
                .options(selectinload(Chat.messages))
            )
        )
        .scalars()
        .all()
    )

    if not chats:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No chats in this project to generate memory from.",
        )

    # Build chronological transcript (oldest chat first, oldest message first).
    transcript_parts: list[str] = []
    for chat in reversed(chats):
        messages = sorted(chat.messages, key=lambda m: m.created_at)
        if not messages:
            continue
        date_str = chat.created_at.strftime("%Y-%m-%d")
        lines = [f'=== CHAT: "{chat.title}" ({date_str}) ===']
        for msg in messages:
            if msg.role not in ("user", "assistant"):
                continue
            content = msg.content or ""
            if len(content) > 600:
                content = content[:600] + "... [truncated]"
            lines.append(f"{msg.role.capitalize()}: {content}")
        transcript_parts.append("\n".join(lines))

    if not transcript_parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project chats contain no user/assistant messages.",
        )

    transcript = "\n\n".join(transcript_parts)

    # Resolve generation model from per-user Settings (same field title-gen uses).
    user_settings = (
        await db.execute(
            select(UserSettings).where(UserSettings.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    gen_model = (
        user_settings.conversation_summarization_model if user_settings else None
    )

    logger.info(
        f"Generating memory for project {project.id} from {len(transcript_parts)} chat(s) "
        f"using model '{gen_model or 'env-default'}'"
    )
    memory_text = await ollama_service.generate_project_memory(
        transcript, model=gen_model
    )

    return ProjectMemoryGenerateResponse(memory=memory_text)
