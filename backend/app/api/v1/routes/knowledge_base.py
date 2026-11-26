"""
Knowledge Base Routes

Handles knowledge source management:
- Document upload and processing
- Website scraping
- Text content management
- Source management (list, delete, reindex)
"""

import os
import uuid
import shutil
from typing import Optional, List
from fastapi import APIRouter, Depends, File, UploadFile, Form, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.tasks.document_tasks import process_document_task
from app.tasks.scraping_tasks import scrape_website_task
from app.tasks.reindex_tasks import reindex_source_task
from app.services.background_tasks import run_with_db_session
from app.schemas.knowledge_base import (
    WebScrapeRequest,
    WebScrapeResponse,
    TextContentCreate,
    TextContentUpdate,
    TextContentResponse,
    KnowledgeSourceResponse,
    KnowledgeSourceList,
    SourceUpdateRequest,
    ReindexRequest,
    ReindexResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    SourceType,
    SourceStatus,
    DocumentUploadResponse,
    ProcessingStatus,
    KnowledgeBaseStats
)
from app.schemas.base import ApiResponse
from app.utils.response import success_response, created_response, message_response, create_response
from app.core.dependencies import (
    get_current_user,
    get_current_organization_id,
    RequirePermission
)
from app.db.models.user import User
from app.db.models.knowledge_base import KnowledgeSource, TextContent, Document, WebPage
from app.services.knowledge_service import KnowledgeService
from app.services.document_processor import is_allowed_file_type, validate_file_size
from app.core.exceptions import ValidationException, NotFoundException
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# DOCUMENT UPLOAD
# ============================================================================

@router.post(
    "/documents/upload",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Upload and process a document (PDF, DOCX, TXT, MD)"
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bot_id: str = Form(...),
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Upload a document for knowledge base indexing.
    
    The document is saved immediately and processed in the background.
    Use the returned source_id to check processing status.
    
    Supported formats:
    - PDF (.pdf)
    - Microsoft Word (.docx)
    - Text files (.txt)
    - Markdown (.md)
    
    **Permissions:** kb:manage
    """
    try:
        # Validate bot exists
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException("Bot not found")
        
        # Validate file type
        if not is_allowed_file_type(file.filename):
            raise ValidationException(
                f"Unsupported file type. Allowed types: PDF, DOCX, TXT, MD"
            )
        
        # Read file to get size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        if not validate_file_size(file_size):
            raise ValidationException(
                f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Create upload directory if not exists
        upload_dir = os.path.join(settings.UPLOAD_DIR, organization_id, bot_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Get MIME type
        file_type = file.content_type or "application/octet-stream"
        
        # Create database records immediately
        source_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())
        
        source = KnowledgeSource(
            id=source_id,
            bot_id=bot_id,
            name=file.filename,
            source_type=SourceType.DOCUMENT,
            status=SourceStatus.PENDING,
            meta_data={"original_filename": file.filename}
        )
        db.add(source)
        
        document = Document(
            id=document_id,
            source_id=source_id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            uploaded_by=current_user.id,
            processing_status="pending"
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document uploaded: {file.filename} (source_id: {source_id})")
        
        # Queue background task with FastAPI BackgroundTasks
        background_tasks.add_task(
            run_with_db_session,
            process_document_task,
            document_id=document_id,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data={
                "id": document_id,
                "source_id": source_id,
                "filename": file.filename,
                "file_size": file_size,
                "file_type": file_type,
                "status": "pending",
                "created_at": document.created_at
            },
            message="Document uploaded and queued for processing",
            status_code=201
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        # Set source status to failed if created
        try:
            if 'source' in locals() and source:
                source.status = SourceStatus.FAILED
                source.error_message = str(e)
                db.commit()
        except Exception as update_error:
            logger.error(f"Error updating failed status: {str(update_error)}")
            db.rollback()
        raise


# ============================================================================
# WEB SCRAPING
# ============================================================================

@router.post(
    "/website/scrape",
    response_model=ApiResponse[WebScrapeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Scrape website",
    description="Scrape content from a website or sitemap"
)
async def scrape_website(
    background_tasks: BackgroundTasks,
    data: WebScrapeRequest,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Scrape website content for knowledge base indexing.
    
    The website is queued for scraping immediately and processed in the background.
    Use the returned source_id to check processing status.
    
    - Supports sitemap.xml parsing
    - Follows links (optional)
    - Respects robots.txt (configurable)
    - Maximum pages limit
    
    **Permissions:** kb:manage
    """
    try:
        # Validate bot exists
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(
            Bot.id == data.bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException("Bot not found")
        
        # Create source record immediately
        source_id = str(uuid.uuid4())
        
        source = KnowledgeSource(
            id=source_id,
            bot_id=data.bot_id,
            name=f"Website: {data.url}",
            source_type=SourceType.WEB,
            status=SourceStatus.PENDING,
            meta_data={
                "url": str(data.url),
                "max_pages": data.max_pages,
                "include_sitemap": data.include_sitemap
            }
        )
        db.add(source)
        db.commit()
        
        logger.info(f"Website scraping queued: {data.url} (source_id: {source_id})")
        
        # Queue background task with FastAPI BackgroundTasks
        background_tasks.add_task(
            run_with_db_session,
            scrape_website_task,
            source_id=source_id,
            url=str(data.url),
            bot_id=data.bot_id,
            organization_id=organization_id,
            max_pages=data.max_pages
        )
        
        return created_response(
            data={
                "source_id": source_id,
                "url": str(data.url),
                "status": "pending",
                "pages_queued": data.max_pages,
                "estimated_time": data.max_pages * 2,  # Rough estimate: 2 seconds per page
                "message": "Website scraping queued for background processing."
            },
            message="Website scraping queued successfully"
        )
        
    except Exception as e:
        logger.error(f"Error queueing website scrape: {str(e)}")
        # Set source status to failed if created
        try:
            if 'source' in locals() and source:
                source.status = SourceStatus.FAILED
                source.error_message = str(e)
                db.commit()
        except Exception as update_error:
            logger.error(f"Error updating failed status: {str(update_error)}")
            db.rollback()
        raise


# ============================================================================
# TEXT CONTENT MANAGEMENT
# ============================================================================

@router.post(
    "/text",
    response_model=ApiResponse[TextContentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create text content",
    description="Create text content for knowledge base"
)
async def create_text_content(
    background_tasks: BackgroundTasks,
    data: TextContentCreate,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Create text content and index it in the knowledge base.
    
    The content is saved immediately and processed in the background.
    Use the returned source_id to check processing status.
    
    **Permissions:** kb:manage
    """
    try:
        # Validate bot exists
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(
            Bot.id == data.bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException("Bot not found")
        
        # Create records immediately
        source_id = str(uuid.uuid4())
        text_content_id = str(uuid.uuid4())
        
        source = KnowledgeSource(
            id=source_id,
            bot_id=data.bot_id,
            name=data.title,
            source_type=SourceType.TEXT,
            status=SourceStatus.PENDING,
            meta_data={"category": data.category, "tags": data.tags}
        )
        db.add(source)
        
        text_content = TextContent(
            id=text_content_id,
            source_id=source_id,
            title=data.title,
            content=data.content,
            category=data.category,
            tags=data.tags or [],
            created_by=current_user.id
        )
        db.add(text_content)
        db.commit()
        
        logger.info(f"Text content created: {data.title} (source_id: {source_id})")
        
        # Queue background task for processing
        background_tasks.add_task(
            run_with_db_session,
            process_text_content_task,
            text_content_id=text_content_id,
            source_id=source_id,
            bot_id=data.bot_id,
            organization_id=organization_id
        )
        
        return created_response(
            data={
                "id": text_content.id,
                "source_id": source_id,
                "title": text_content.title,
                "content": text_content.content,
                "category": text_content.category,
                "tags": text_content.tags,
                "created_by": text_content.created_by,
                "created_at": text_content.created_at,
                "updated_at": text_content.updated_at,
                "chunk_count": 0  # Will be updated after processing
            },
            message="Text content created and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Error creating text content: {str(e)}")
        # Set source status to failed if created
        try:
            if 'source' in locals() and source:
                source.status = SourceStatus.FAILED
                source.error_message = str(e)
                db.commit()
        except Exception as update_error:
            logger.error(f"Error updating failed status: {str(update_error)}")
            db.rollback()
        raise


@router.get(
    "/text",
    response_model=ApiResponse[KnowledgeSourceList],
    summary="List text content",
    description="List all text content for a bot"
)
async def list_text_content(
    bot_id: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequirePermission("kb:view")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    List text content for a specific bot.
    
    **Permissions:** kb:view
    """
    try:
        # Query text content
        query = db.query(TextContent).join(KnowledgeSource).filter(
            KnowledgeSource.bot_id == bot_id,
            KnowledgeSource.source_type == SourceType.TEXT
        )
        
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        
        # Convert to response schema
        text_contents = [
            {
                "id": item.id,
                "source_id": item.source_id,
                "title": item.title,
                "content": item.content[:500] + "..." if len(item.content) > 500 else item.content,
                "category": item.category,
                "tags": item.tags,
                "created_by": item.created_by,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            }
            for item in items
        ]
        
        return success_response(
            data={
                "items": text_contents,
                "total": total,
                "page": skip // limit + 1,
                "page_size": limit
            },
            message="Text content retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error listing text content: {str(e)}")
        raise


@router.put(
    "/text/{text_content_id}",
    response_model=ApiResponse[TextContentResponse],
    summary="Update text content",
    description="Update existing text content"
)
async def update_text_content(
    text_content_id: str,
    data: TextContentUpdate,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Update text content and reindex if necessary.
    
    **Permissions:** kb:manage
    """
    try:
        # Get text content
        text_content = db.query(TextContent).filter(
            TextContent.id == text_content_id
        ).first()
        
        if not text_content:
            raise NotFoundException("Text content not found")
        
        # Update fields
        if data.title is not None:
            text_content.title = data.title
        if data.content is not None:
            text_content.content = data.content
        if data.category is not None:
            text_content.category = data.category
        if data.tags is not None:
            text_content.tags = data.tags
        
        db.commit()
        
        # Reindex if content changed
        if data.content is not None:
            knowledge_service = KnowledgeService(db)
            await knowledge_service.reindex_source(
                text_content.source_id,
                organization_id
            )
        
        return success_response(
            data={"id": text_content.id, "title": text_content.title},
            message="Text content updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error updating text content: {str(e)}")
        db.rollback()
        raise


@router.delete(
    "/text/{text_content_id}",
    summary="Delete text content",
    description="Delete text content and its source"
)
async def delete_text_content(
    text_content_id: str,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Delete text content.
    
    **Permissions:** kb:manage
    """
    try:
        # Get text content
        text_content = db.query(TextContent).filter(
            TextContent.id == text_content_id
        ).first()
        
        if not text_content:
            raise NotFoundException("Text content not found")
        
        source_id = text_content.source_id
        
        # Delete source (cascades to text content)
        knowledge_service = KnowledgeService(db)
        await knowledge_service.delete_source(source_id, organization_id)
        
        return message_response(
            message="Text content deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting text content: {str(e)}")
        raise


# ============================================================================
# SOURCE MANAGEMENT
# ============================================================================

@router.get(
    "/sources",
    response_model=ApiResponse[KnowledgeSourceList],
    summary="List knowledge sources",
    description="List all knowledge sources with filtering"
)
async def list_sources(
    bot_id: Optional[str] = Query(None),
    source_type: Optional[SourceType] = Query(None),
    status: Optional[SourceStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequirePermission("kb:view")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    List knowledge sources with optional filtering.
    
    **Permissions:** kb:view
    """
    try:
        knowledge_service = KnowledgeService(db)
        
        sources = knowledge_service.list_sources(
            bot_id=bot_id,
            organization_id=organization_id,
            source_type=source_type,
            status=status,
            skip=skip,
            limit=limit
        )
        
        # Get total count
        from app.db.models.bot import Bot
        query = db.query(KnowledgeSource).join(Bot).filter(
            Bot.organization_id == organization_id
        )
        if bot_id:
            query = query.filter(KnowledgeSource.bot_id == bot_id)
        if source_type:
            query = query.filter(KnowledgeSource.source_type == source_type)
        if status:
            query = query.filter(KnowledgeSource.status == status)
        
        total = query.count()
        
        # Convert to response format
        sources_data = []
        for source in sources:
            sources_data.append({
                "id": source.id,
                "bot_id": source.bot_id,
                "name": source.name,
                "source_type": source.source_type.value,
                "status": source.status.value,
                "metadata": source.meta_data,
                "chunk_count": source.chunk_count,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
                "last_indexed_at": source.last_indexed_at
            })
        
        return success_response(
            data={
                "sources": sources_data,
                "total": total,
                "page": skip // limit + 1,
                "page_size": limit
            },
            message="Sources retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error listing sources: {str(e)}")
        raise


@router.get(
    "/sources/{source_id}",
    response_model=ApiResponse[KnowledgeSourceResponse],
    summary="Get source details",
    description="Get detailed information about a knowledge source"
)
async def get_source(
    source_id: str,
    current_user: User = Depends(RequirePermission("kb:view")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific knowledge source.
    
    **Permissions:** kb:view
    """
    try:
        knowledge_service = KnowledgeService(db)
        source = knowledge_service.get_source(source_id, organization_id)
        
        # Build response data
        source_data = {
            "id": source.id,
            "bot_id": source.bot_id,
            "name": source.name,
            "source_type": source.source_type.value,
            "status": source.status.value,
            "metadata": source.meta_data,
            "chunk_count": source.chunk_count,
            "error_message": source.error_message,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            "last_indexed_at": source.last_indexed_at
        }
        
        # Add type-specific data
        if source.source_type == SourceType.DOCUMENT and source.document:
            source_data["document"] = {
                "filename": source.document.filename,
                "file_size": source.document.file_size,
                "file_type": source.document.file_type,
                "page_count": source.document.page_count,
                "processing_status": source.document.processing_status
            }
        elif source.source_type == SourceType.WEB:
            source_data["webpages"] = [
                {
                    "url": wp.url,
                    "title": wp.title,
                    "is_indexed": wp.is_indexed
                }
                for wp in source.webpages[:10]  # First 10 pages
            ]
            source_data["webpage_count"] = len(source.webpages)
        elif source.source_type == SourceType.TEXT and source.text_content:
            source_data["text_content"] = {
                "title": source.text_content.title,
                "content_length": len(source.text_content.content),
                "category": source.text_content.category,
                "tags": source.text_content.tags
            }
        
        return success_response(
            data=source_data,
            message="Source details retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting source: {str(e)}")
        raise


@router.get(
    "/sources/{source_id}/status",
    response_model=ApiResponse[ProcessingStatus],
    summary="Get processing status",
    description="Get the current processing status of a knowledge source"
)
async def get_source_status(
    source_id: str,
    current_user: User = Depends(RequirePermission("kb:view")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get the current processing status of a knowledge source.
    
    Use this endpoint to poll for status updates after uploading/scraping.
    
    **Statuses:**
    - `pending`: Waiting to be processed
    - `processing`: Currently being processed
    - `indexed`: Successfully processed and indexed
    - `failed`: Processing failed
    
    **Permissions:** kb:view
    """
    try:
        # Get source
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id
        ).first()
        
        if not source:
            raise NotFoundException("Source not found")
        
        # Verify tenant access
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(
            Bot.id == source.bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException("Source not found")
        
        # Build status response
        status_data = {
            "source_id": source.id,
            "status": source.status.value,
            "chunk_count": source.chunk_count or 0,
            "error_message": source.error_message,
            "last_indexed_at": source.last_indexed_at,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            # Required fields for ProcessingStatus schema
            "progress": 0.0,  # Default progress
            "total_items": 0,
            "processed_items": 0,
            "failed_items": 0,
            "started_at": source.created_at,  # Use created_at as started_at
        }
        
        # Add type-specific status info
        if source.source_type == SourceType.DOCUMENT and source.document:
            status_data["processing_status"] = source.document.processing_status
            status_data["file_info"] = {
                "filename": source.document.filename,
                "file_size": source.document.file_size,
                "page_count": source.document.page_count
            }
            # Calculate progress for documents
            if source.document.page_count and source.document.page_count > 0:
                status_data["total_items"] = source.document.page_count
                status_data["processed_items"] = source.chunk_count or 0
                status_data["progress"] = min(100.0, (status_data["processed_items"] / status_data["total_items"]) * 100)
        elif source.source_type == SourceType.WEB:
            webpage_count = len(source.webpages)
            indexed_count = sum(1 for wp in source.webpages if wp.is_indexed)
            status_data["scraping_progress"] = {
                "total_pages": webpage_count,
                "indexed_pages": indexed_count,
                "pending_pages": webpage_count - indexed_count
            }
            # Calculate progress for web scraping
            if webpage_count > 0:
                status_data["total_items"] = webpage_count
                status_data["processed_items"] = indexed_count
                status_data["progress"] = (indexed_count / webpage_count) * 100
        elif source.source_type == SourceType.TEXT and source.text_content:
            status_data["text_info"] = {
                "title": source.text_content.title,
                "content_length": len(source.text_content.content)
            }
            # Text content is simple, mark as 100% if indexed
            if source.status.value == 'indexed':
                status_data["progress"] = 100.0
                status_data["total_items"] = 1
                status_data["processed_items"] = 1
        
        return success_response(
            data=status_data,
            message="Status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        raise


@router.delete(
    "/sources/{source_id}",
    response_model=ApiResponse[dict],
    summary="Delete source",
    description="Delete a knowledge source and all its data"
)
async def delete_source(
    source_id: str,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Delete a knowledge source.
    
    This will delete:
    - The source record
    - All chunks in the database
    - All vectors in Qdrant
    - Associated documents/webpages/text content
    
    **Permissions:** kb:manage
    """
    try:
        knowledge_service = KnowledgeService(db)
        await knowledge_service.delete_source(source_id, organization_id)
        
        return create_response(
            data=None,
            message="Source deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting source: {str(e)}")
        raise


@router.put(
    "/sources/{source_id}",
    response_model=ApiResponse[KnowledgeSourceResponse],
    summary="Update knowledge source",
    description="Update a knowledge source (name, URL, content, metadata)"
)
async def update_source(
    source_id: str,
    data: SourceUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Update a knowledge source.
    
    Supports updating:
    - **Name**: All source types
    - **URL**: Web sources only
    - **Content**: Text sources only
    - **Metadata**: All source types
    
    Content updates trigger reindexing in the background.
    
    **Permissions:** kb:manage
    """
    try:
        # Get and verify source
        knowledge_service = KnowledgeService(db)
        source = knowledge_service.get_source(source_id, organization_id)
        
        # Track if content changed (requires reindexing)
        needs_reindex = False
        
        # Update name if provided
        if data.name is not None:
            source.name = data.name
        
        # Update metadata if provided
        if data.metadata is not None:
            source.meta_data = {**(source.meta_data or {}), **data.metadata}
        
        # Handle type-specific updates
        if source.source_type == SourceType.WEB:
            # Update web source URL
            if data.url is not None:
                if not source.meta_data:
                    source.meta_data = {}
                source.meta_data['url'] = str(data.url)
                needs_reindex = True
                
        elif source.source_type == SourceType.TEXT:
            # Update text content
            if data.content is not None:
                text_content = db.query(TextContent).filter(
                    TextContent.source_id == source_id
                ).first()
                
                if text_content:
                    text_content.content = data.content
                    needs_reindex = True
        
        # Save changes
        db.commit()
        db.refresh(source)
        
        logger.info(f"Source updated: {source_id}")
        
        # Trigger reindexing if content changed
        if needs_reindex:
            source.status = SourceStatus.PENDING
            source.error_message = None
            db.commit()
            
            background_tasks.add_task(
                run_with_db_session,
                reindex_source_task,
                source_id=source_id,
                organization_id=organization_id
            )
            logger.info(f"Reindexing queued for source: {source_id}")
        
        return success_response(
            data={
                "id": source.id,
                "bot_id": source.bot_id,
                "name": source.name,
                "source_type": source.source_type.value,
                "status": source.status.value,
                "metadata": source.meta_data,
                "chunk_count": source.chunk_count,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
                "last_indexed_at": source.last_indexed_at
            },
            message="Source updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error updating source: {str(e)}")
        db.rollback()
        raise


@router.put(
    "/documents/{document_id}/file",
    response_model=ApiResponse[DocumentUploadResponse],
    summary="Update document file",
    description="Replace a document file and trigger reindexing"
)
async def update_document_file(
    document_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Replace an existing document file.
    
    This will:
    - Delete the old file from storage
    - Upload the new file
    - Trigger reindexing in the background
    
    **Permissions:** kb:manage
    """
    try:
        # Get document
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()
        
        if not document:
            raise NotFoundException("Document not found")
        
        # Get associated source
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == document.source_id
        ).first()
        
        if not source:
            raise NotFoundException("Source not found")
        
        # Verify bot belongs to organization
        from app.db.models.bot import Bot
        bot = db.query(Bot).filter(
            Bot.id == source.bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException("Document not found")
        
        # Validate file type
        if not is_allowed_file_type(file.filename):
            raise ValidationException(
                f"Unsupported file type. Allowed types: PDF, DOCX, TXT, MD"
            )
        
        # Read and validate file size
        file_content = await file.read()
        file_size = len(file_content)
        
        if not validate_file_size(file_size):
            raise ValidationException(
                f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Delete old file
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
                logger.info(f"Deleted old file: {document.file_path}")
            except Exception as e:
                logger.warning(f"Could not delete old file: {str(e)}")
        
        # Create new file path
        upload_dir = os.path.join(settings.UPLOAD_DIR, organization_id, source.bot_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save new file
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Update document record
        document.filename = file.filename
        document.file_path = file_path
        document.file_size = file_size
        document.file_type = file.content_type or "application/octet-stream"
        document.processing_status = "pending"
        
        # Update source status
        source.status = SourceStatus.PENDING
        source.error_message = None
        source.meta_data = {
            **(source.meta_data or {}),
            "original_filename": file.filename
        }
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document file updated: {document_id}")
        
        # Queue reindexing task
        background_tasks.add_task(
            run_with_db_session,
            process_document_task,
            document_id=document_id,
            bot_id=source.bot_id,
            organization_id=organization_id
        )
        
        return success_response(
            data={
                "id": document_id,
                "source_id": source.id,
                "filename": file.filename,
                "file_size": file_size,
                "file_type": document.file_type,
                "status": "pending",
                "created_at": document.created_at
            },
            message="Document file updated and queued for reindexing"
        )
        
    except Exception as e:
        logger.error(f"Error updating document file: {str(e)}")
        db.rollback()
        raise


@router.post(
    "/sources/{source_id}/reindex",
    response_model=ApiResponse[ReindexResponse],
    summary="Reindex source",
    description="Reindex a knowledge source"
)
async def reindex_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Reindex a knowledge source.
    
    This will:
    - Delete existing chunks and vectors
    - Re-process the source content
    - Generate new embeddings
    - Re-index in Qdrant
    
    The reindexing is processed in the background.
    Use the status endpoint to check progress.
    
    **Permissions:** kb:manage
    """
    try:
        # Verify source exists and belongs to organization
        knowledge_service = KnowledgeService(db)
        source = knowledge_service.get_source(source_id, organization_id)
        
        # Update status to pending
        source.status = SourceStatus.PENDING
        source.error_message = None
        db.commit()
        
        logger.info(f"Reindexing queued for source: {source_id}")
        
        # Queue background task
        background_tasks.add_task(
            run_with_db_session,
            reindex_source_task,
            source_id=source_id,
            organization_id=organization_id
        )
        
        return success_response(
            data={
                "source_id": source_id,
                "status": "pending",
                "message": "Reindexing queued for background processing."
            },
            message="Reindexing started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error queueing reindex: {str(e)}")
        raise


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post(
    "/sources/bulk-delete",
    response_model=ApiResponse[BulkDeleteResponse],
    summary="Bulk delete sources",
    description="Delete multiple knowledge sources"
)
async def bulk_delete_sources(
    data: BulkDeleteRequest,
    current_user: User = Depends(RequirePermission("kb:manage")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Delete multiple knowledge sources at once.
    
    **Permissions:** kb:manage
    """
    try:
        knowledge_service = KnowledgeService(db)
        
        deleted_count = 0
        failed_ids = []
        
        for source_id in data.source_ids:
            try:
                await knowledge_service.delete_source(source_id, organization_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete source {source_id}: {str(e)}")
                failed_ids.append(source_id)
        
        return create_response(
            data={
                "deleted_count": deleted_count,
                "failed_ids": failed_ids
            },
            message=f"Deleted {deleted_count} sources"
        )
        
    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        raise


# ============================================================================
# STATISTICS
# ============================================================================

@router.get(
    "/stats",
    response_model=ApiResponse[KnowledgeBaseStats],
    summary="Get knowledge base statistics",
    description="Get statistics about knowledge base for a bot or organization"
)
async def get_kb_stats(
    bot_id: Optional[str] = Query(None),
    current_user: User = Depends(RequirePermission("kb:view")),
    organization_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get knowledge base statistics.
    
    **Permissions:** kb:view
    """
    try:
        from app.db.models.bot import Bot
        from app.db.models.knowledge_base import Document, WebPage, Chunk
        from sqlalchemy import func
        
        # Base query
        sources_query = db.query(KnowledgeSource).join(Bot).filter(
            Bot.organization_id == organization_id
        )
        
        if bot_id:
            sources_query = sources_query.filter(KnowledgeSource.bot_id == bot_id)
        
        # Get counts by type
        total_sources = sources_query.count()
        
        doc_count = sources_query.filter(
            KnowledgeSource.source_type == SourceType.DOCUMENT
        ).count()
        
        web_count = sources_query.filter(
            KnowledgeSource.source_type == SourceType.WEB
        ).count()
        
        text_count = sources_query.filter(
            KnowledgeSource.source_type == SourceType.TEXT
        ).count()
        
        indexed_count = sources_query.filter(
            KnowledgeSource.status == SourceStatus.INDEXED
        ).count()
        
        pending_count = sources_query.filter(
            KnowledgeSource.status == SourceStatus.PENDING
        ).count()
        
        failed_count = sources_query.filter(
            KnowledgeSource.status == SourceStatus.FAILED
        ).count()
        
        # Get chunk count
        chunks_query = db.query(Chunk).join(Bot).filter(
            Bot.organization_id == organization_id
        )
        if bot_id:
            chunks_query = chunks_query.filter(Chunk.bot_id == bot_id)
        
        total_chunks = chunks_query.count()
        
        # Calculate total size in bytes
        # 1. Sum file sizes from documents
        doc_size_query = db.query(func.coalesce(func.sum(Document.file_size), 0)).join(
            KnowledgeSource
        ).join(Bot).filter(
            Bot.organization_id == organization_id
        )
        if bot_id:
            doc_size_query = doc_size_query.filter(KnowledgeSource.bot_id == bot_id)
        
        total_doc_size = doc_size_query.scalar() or 0
        
        # 2. Calculate size from webpage content (length in bytes)
        webpage_size_query = db.query(func.coalesce(func.sum(func.length(WebPage.content)), 0)).join(
            KnowledgeSource
        ).join(Bot).filter(
            Bot.organization_id == organization_id,
            WebPage.content.isnot(None)
        )
        if bot_id:
            webpage_size_query = webpage_size_query.filter(KnowledgeSource.bot_id == bot_id)
        
        total_webpage_size = webpage_size_query.scalar() or 0
        
        # 3. Calculate size from text content (length in bytes)
        text_size_query = db.query(func.coalesce(func.sum(func.length(TextContent.content)), 0)).join(
            KnowledgeSource
        ).join(Bot).filter(
            Bot.organization_id == organization_id
        )
        if bot_id:
            text_size_query = text_size_query.filter(KnowledgeSource.bot_id == bot_id)
        
        total_text_size = text_size_query.scalar() or 0
        
        # Sum all sizes
        total_size_bytes = total_doc_size + total_webpage_size + total_text_size
        
        stats = {
            "total_sources": total_sources,
            "total_documents": doc_count,
            "total_webpages": web_count,
            "total_text_contents": text_count,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size_bytes,
            "indexed_sources": indexed_count,
            "pending_sources": pending_count,
            "failed_sources": failed_count,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return success_response(
            data=stats,
            message="Statistics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise


from datetime import datetime
