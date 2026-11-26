"""
Knowledge Service

High-level service that orchestrates knowledge base operations:
- Document upload and processing
- Web scraping
- Text content management
- Embedding generation and indexing
- Source management
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.models.knowledge_base import (
    KnowledgeSource,
    Document,
    WebPage,
    TextContent,
    Chunk,
    SourceType,
    SourceStatus
)
from app.db.models.bot import Bot
from app.services.document_processor import DocumentProcessor
from app.services.scraper_service import WebScraper
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import QdrantService
from app.core.exceptions import (
    NotFoundException,
    ProcessingException
)
from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Service for managing knowledge base operations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize knowledge service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.document_processor = DocumentProcessor()
        # Use lazy initialization for expensive services
        self._embedding_service = None
        self._qdrant_service = None
    
    @property
    def embedding_service(self):
        """Lazy-load embedding service only when needed."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service
    
    @property
    def qdrant_service(self):
        """Lazy-load Qdrant service only when needed."""
        if self._qdrant_service is None:
            self._qdrant_service = QdrantService()
        return self._qdrant_service

    
    # ========================================================================
    # DOCUMENT OPERATIONS
    # ========================================================================
    
    async def upload_document(
        self,
        file_path: str,
        filename: str,
        file_size: int,
        file_type: str,
        bot_id: str,
        organization_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Upload and process a document.
        
        Args:
            file_path: Path to uploaded file
            filename: Original filename
            file_size: File size in bytes
            file_type: MIME type
            bot_id: Bot ID
            organization_id: Organization ID
            user_id: User ID who uploaded
            
        Returns:
            Dict: Upload result with source and document info
        """
        try:
            # Validate bot exists and belongs to organization
            bot = self.db.query(Bot).filter(
                Bot.id == bot_id,
                Bot.organization_id == organization_id
            ).first()
            
            if not bot:
                raise NotFoundException("Bot not found")
            
            # Create knowledge source
            source = KnowledgeSource(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                name=filename,
                source_type=SourceType.DOCUMENT,
                status=SourceStatus.PENDING,
                meta_data={"original_filename": filename}
            )
            self.db.add(source)
            
            # Create document record
            document = Document(
                id=str(uuid.uuid4()),
                source_id=source.id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                uploaded_by=user_id,
                processing_status="pending"
            )
            self.db.add(document)
            self.db.commit()
            
            logger.info(f"Document uploaded: {filename} (source_id: {source.id})")
            
            # Process document asynchronously (in background)
            try:
                await self._process_document(source.id, organization_id)
            except Exception as e:
                logger.error(f"Error processing document {source.id}: {str(e)}")
                # Update status to failed
                source.status = SourceStatus.FAILED
                source.error_message = str(e)
                document.processing_status = "failed"
                document.error_message = str(e)
                self.db.commit()
            
            return {
                "source_id": source.id,
                "document_id": document.id,
                "filename": filename,
                "status": source.status.value
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error uploading document: {str(e)}")
            raise
    
    async def _process_document(
        self,
        source_id: str,
        organization_id: str
    ):
        """
        Process document: extract text, chunk, embed, and index.
        
        Args:
            source_id: Source ID
            organization_id: Organization ID
        """
        try:
            # Get source and document
            source = self.db.query(KnowledgeSource).filter(
                KnowledgeSource.id == source_id
            ).first()
            
            if not source or not source.document:
                raise NotFoundException("Source or document not found")
            
            document = source.document
            
            # Update status to processing
            source.status = SourceStatus.PROCESSING
            document.processing_status = "processing"
            self.db.commit()
            
            logger.info(f"Processing document: {document.filename}")
            
            # Extract text and create chunks
            result = self.document_processor.process_document(
                file_path=document.file_path,
                source_metadata={
                    "source_id": source_id,
                    "document_id": document.id,
                    "filename": document.filename
                }
            )
            
            if not result.get("success"):
                raise ProcessingException(result.get("error", "Unknown error"))
            
            chunks_data = result.get("chunks", [])
            
            if not chunks_data:
                raise ProcessingException("No chunks generated from document")
            
            # Update document metadata
            document.page_count = result.get("metadata", {}).get("page_count")
            document.processing_status = "indexed"
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks_data)} chunks")
            chunks_with_embeddings = self.embedding_service.embed_chunks(chunks_data)
            
            # Save chunks to database and Qdrant
            await self._save_chunks(
                chunks_with_embeddings,
                source_id,
                source.bot_id,
                organization_id
            )
            
            # Update source status
            source.status = SourceStatus.INDEXED
            source.chunk_count = len(chunks_data)
            source.last_indexed_at = datetime.utcnow().isoformat()
            
            self.db.commit()
            
            logger.info(f"Document processed successfully: {document.filename}")
            
        except Exception as e:
            logger.error(f"Error in document processing: {str(e)}")
            # Update source and document status to failed
            try:
                if source:
                    source.status = SourceStatus.FAILED
                    source.error_message = str(e)
                if document:
                    document.processing_status = "failed"
                    document.error_message = str(e)
                self.db.commit()
            except Exception as commit_error:
                logger.error(f"Error updating failed status: {str(commit_error)}")
                self.db.rollback()
            raise
    
    # ========================================================================
    # WEB SCRAPING OPERATIONS
    # ========================================================================
    
    async def scrape_website(
        self,
        url: str,
        bot_id: str,
        organization_id: str,
        max_pages: int = 10,
        follow_links: bool = True,
        use_sitemap: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape website and index content.
        
        Args:
            url: URL to scrape
            bot_id: Bot ID
            organization_id: Organization ID
            max_pages: Maximum pages to scrape
            follow_links: Whether to follow links
            use_sitemap: Whether to use sitemap
            
        Returns:
            Dict: Scraping result
        """
        try:
            # Validate bot
            bot = self.db.query(Bot).filter(
                Bot.id == bot_id,
                Bot.organization_id == organization_id
            ).first()
            
            if not bot:
                raise NotFoundException("Bot not found")
            
            # Create knowledge source
            source = KnowledgeSource(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                name=f"Website: {url}",
                source_type=SourceType.WEB,
                status=SourceStatus.PENDING,
                meta_data={"url": url, "max_pages": max_pages}
            )
            self.db.add(source)
            self.db.commit()
            
            # Start scraping
            source.status = SourceStatus.PROCESSING
            self.db.commit()
            
            scraper = WebScraper(
                max_pages=max_pages,
                follow_links=follow_links
            )
            
            result = await scraper.scrape_website(url, use_sitemap=use_sitemap)
            
            # Save scraped pages
            for page_data in result.get("pages", []):
                webpage = WebPage(
                    id=str(uuid.uuid4()),
                    source_id=source.id,
                    url=page_data["url"],
                    title=page_data.get("title"),
                    content=page_data.get("content"),
                    status_code=page_data.get("status_code"),
                    scraped_at=page_data.get("scraped_at"),
                    is_indexed=False,
                    meta_data=page_data.get("metadata", {})
                )
                self.db.add(webpage)
            
            self.db.commit()
            
            # Process and index pages
            await self._process_webpages(source.id, organization_id)
            
            return {
                "source_id": source.id,
                "pages_scraped": result.get("successful_pages", 0),
                "pages_failed": result.get("failed_count", 0),
                "status": source.status.value
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error scraping website: {str(e)}")
            raise
    
    async def _process_webpages(
        self,
        source_id: str,
        organization_id: str
    ):
        """
        Process scraped webpages: chunk, embed, and index.
        
        Args:
            source_id: Source ID
            organization_id: Organization ID
        """
        try:
            source = self.db.query(KnowledgeSource).filter(
                KnowledgeSource.id == source_id
            ).first()
            
            if not source:
                raise NotFoundException("Source not found")
            
            all_chunks = []
            
            # Process each webpage
            for webpage in source.webpages:
                if not webpage.content:
                    continue
                
                # Chunk content
                chunks = self.document_processor.chunk_text(
                    webpage.content,
                    metadata={
                        "source_id": source_id,
                        "webpage_id": webpage.id,
                        "url": webpage.url,
                        "title": webpage.title
                    }
                )
                
                all_chunks.extend(chunks)
                webpage.is_indexed = True
            
            if all_chunks:
                # Generate embeddings
                chunks_with_embeddings = self.embedding_service.embed_chunks(all_chunks)
                
                # Save chunks
                await self._save_chunks(
                    chunks_with_embeddings,
                    source_id,
                    source.bot_id,
                    organization_id
                )
            
            # Update source
            source.status = SourceStatus.INDEXED
            source.chunk_count = len(all_chunks)
            source.last_indexed_at = datetime.utcnow().isoformat()
            
            self.db.commit()
            
            logger.info(f"Processed {len(all_chunks)} chunks from webpages")
            
        except Exception as e:
            logger.error(f"Error processing webpages: {str(e)}")
            # Update source status to failed
            try:
                if source:
                    source.status = SourceStatus.FAILED
                    source.error_message = str(e)
                    self.db.commit()
            except Exception as commit_error:
                logger.error(f"Error updating failed status: {str(commit_error)}")
                self.db.rollback()
            raise
    
    # ========================================================================
    # TEXT CONTENT OPERATIONS
    # ========================================================================
    
    async def create_text_content(
        self,
        title: str,
        content: str,
        bot_id: str,
        organization_id: str,
        user_id: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create text content and index it.
        
        Args:
            title: Content title
            content: Text content
            bot_id: Bot ID
            organization_id: Organization ID
            user_id: User ID
            category: Content category
            tags: Content tags
            
        Returns:
            Dict: Created content info
        """
        try:
            # Validate bot
            bot = self.db.query(Bot).filter(
                Bot.id == bot_id,
                Bot.organization_id == organization_id
            ).first()
            
            if not bot:
                raise NotFoundException("Bot not found")
            
            # Create knowledge source
            source = KnowledgeSource(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                name=title,
                source_type=SourceType.TEXT,
                status=SourceStatus.PENDING
            )
            self.db.add(source)
            
            # Create text content
            text_content = TextContent(
                id=str(uuid.uuid4()),
                source_id=source.id,
                title=title,
                content=content,
                category=category,
                tags=tags or [],
                created_by=user_id
            )
            self.db.add(text_content)
            self.db.commit()
            
            # Process and index
            await self._process_text_content(source.id, organization_id)
            
            return {
                "source_id": source.id,
                "text_content_id": text_content.id,
                "title": title,
                "status": source.status.value
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating text content: {str(e)}")
            raise
    
    async def _process_text_content(
        self,
        source_id: str,
        organization_id: str
    ):
        """
        Process text content: chunk, embed, and index.
        
        Args:
            source_id: Source ID
            organization_id: Organization ID
        """
        try:
            source = self.db.query(KnowledgeSource).filter(
                KnowledgeSource.id == source_id
            ).first()
            
            if not source or not source.text_content:
                raise NotFoundException("Source or text content not found")
            
            text_content = source.text_content
            
            source.status = SourceStatus.PROCESSING
            self.db.commit()
            
            # Chunk content
            chunks = self.document_processor.chunk_text(
                text_content.content,
                metadata={
                    "source_id": source_id,
                    "text_content_id": text_content.id,
                    "title": text_content.title,
                    "category": text_content.category,
                    "tags": text_content.tags
                }
            )
            
            if chunks:
                # Generate embeddings
                chunks_with_embeddings = self.embedding_service.embed_chunks(chunks)
                
                # Save chunks
                await self._save_chunks(
                    chunks_with_embeddings,
                    source_id,
                    source.bot_id,
                    organization_id
                )
            
            # Update source
            source.status = SourceStatus.INDEXED
            source.chunk_count = len(chunks)
            source.last_indexed_at = datetime.utcnow().isoformat()
            
            self.db.commit()
            
            logger.info(f"Processed text content: {text_content.title}")
            
        except Exception as e:
            logger.error(f"Error processing text content: {str(e)}")
            # Update source status to failed
            try:
                if source:
                    source.status = SourceStatus.FAILED
                    source.error_message = str(e)
                    self.db.commit()
            except Exception as commit_error:
                logger.error(f"Error updating failed status: {str(commit_error)}")
                self.db.rollback()
            raise
    
    # ========================================================================
    # CHUNK MANAGEMENT
    # ========================================================================
    
    async def _save_chunks(
        self,
        chunks_data: List[Dict[str, Any]],
        source_id: str,
        bot_id: str,
        organization_id: str,
        source_type: str = None
    ):
        """
        Save chunks to database and Qdrant.
        
        Args:
            chunks_data: List of chunk dictionaries with embeddings
            source_id: Source ID
            bot_id: Bot ID
            organization_id: Organization ID
            source_type: Source type (document, web, text)
        """
        try:
            # Get source_type from database if not provided
            if source_type is None:
                source = self.db.query(KnowledgeSource).filter(
                    KnowledgeSource.id == source_id
                ).first()
                if source:
                    source_type = source.source_type.value
                else:
                    raise NotFoundException(f"Source {source_id} not found")
            
            db_chunks = []
            qdrant_points = []
            
            for chunk_data in chunks_data:
                chunk_id = str(uuid.uuid4())
                
                # Create database chunk
                chunk = Chunk(
                    id=chunk_id,
                    source_id=source_id,
                    bot_id=bot_id,
                    organization_id=organization_id,
                    content=chunk_data["content"],
                    chunk_index=chunk_data["chunk_index"],
                    meta_data=chunk_data.get("metadata", {}),
                    is_active=True
                )
                db_chunks.append(chunk)
                
                # Prepare base payload for Qdrant point
                payload = {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "bot_id": bot_id,
                    "organization_id": organization_id,
                    "source_type": source_type,
                    "content": chunk_data["content"],
                    "metadata": chunk_data.get("metadata", {}),
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Add source-specific IDs from metadata if available
                chunk_metadata = chunk_data.get("metadata", {})
                if "document_id" in chunk_metadata:
                    payload["document_id"] = chunk_metadata["document_id"]
                if "webpage_id" in chunk_metadata:
                    payload["webpage_id"] = chunk_metadata["webpage_id"]
                if "text_content_id" in chunk_metadata:
                    payload["text_content_id"] = chunk_metadata["text_content_id"]
                
                # Prepare Qdrant point with complete payload
                qdrant_points.append({
                    "id": chunk_id,
                    "vector": chunk_data["embedding"],
                    "payload": payload
                })
            
            # Save to database
            self.db.bulk_save_objects(db_chunks)
            self.db.commit()
            
            # Save to Qdrant
            collection_name = f"bot_{bot_id}"
            
            # Create collection with text index if it doesn't exist
            if not self.qdrant_service.collection_exists(collection_name):
                self.qdrant_service.create_collection_with_text_index(
                    collection_name=collection_name,
                    vector_size=settings.EMBEDDING_DIMENSION,
                    distance="Cosine"
                )
            
            # Insert points
            self.qdrant_service.insert_vectors(
                collection_name=collection_name,
                vectors=[point["vector"] for point in qdrant_points],
                payloads=[point["payload"] for point in qdrant_points],
                ids=[point["id"] for point in qdrant_points]
            )
            
            logger.info(f"Saved {len(db_chunks)} chunks to database and Qdrant")
            
        except Exception as e:
            logger.error(f"Error saving chunks: {str(e)}")
            raise
    
    # ========================================================================
    # SOURCE MANAGEMENT
    # ========================================================================
    
    def get_source(self, source_id: str, organization_id: str) -> KnowledgeSource:
        """Get source by ID with organization check."""
        source = self.db.query(KnowledgeSource).join(Bot).filter(
            KnowledgeSource.id == source_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not source:
            raise NotFoundException("Source not found")
        
        return source
    
    def list_sources(
        self,
        bot_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        source_type: Optional[SourceType] = None,
        status: Optional[SourceStatus] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[KnowledgeSource]:
        """List knowledge sources with filters."""
        query = self.db.query(KnowledgeSource).join(Bot)
        
        if organization_id:
            query = query.filter(Bot.organization_id == organization_id)
        
        if bot_id:
            query = query.filter(KnowledgeSource.bot_id == bot_id)
        
        if source_type:
            query = query.filter(KnowledgeSource.source_type == source_type)
        
        if status:
            query = query.filter(KnowledgeSource.status == status)
        
        return query.offset(skip).limit(limit).all()
    
    async def delete_source(
        self,
        source_id: str,
        organization_id: str
    ):
        """Delete source and all associated data."""
        try:
            source = self.get_source(source_id, organization_id)
            
            # Delete from Qdrant
            collection_name = f"bot_{source.bot_id}"
            if self.qdrant_service.collection_exists(collection_name):
                # Delete points by source_id filter
                self.qdrant_service.delete_points_by_filter(
                    collection_name=collection_name,
                    filter_dict={"source_id": source_id}
                )
            
            # Delete from database (cascades to chunks, documents, etc.)
            self.db.delete(source)
            self.db.commit()
            
            logger.info(f"Deleted source: {source_id}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting source: {str(e)}")
            raise
    
    async def reindex_source(
        self,
        source_id: str,
        organization_id: str
    ):
        """Reindex an existing source."""
        try:
            source = self.get_source(source_id, organization_id)
            
            # Delete existing chunks
            self.db.query(Chunk).filter(Chunk.source_id == source_id).delete()
            
            # Delete from Qdrant
            collection_name = f"bot_{source.bot_id}"
            if self.qdrant_service.collection_exists(collection_name):
                self.qdrant_service.delete_points_by_filter(
                    collection_name=collection_name,
                    filter_dict={"source_id": source_id}
                )
            
            # Reprocess based on source type
            if source.source_type == SourceType.DOCUMENT:
                await self._process_document(source_id, organization_id)
            elif source.source_type == SourceType.WEB:
                await self._process_webpages(source_id, organization_id)
            elif source.source_type == SourceType.TEXT:
                await self._process_text_content(source_id, organization_id)
            
            logger.info(f"Reindexed source: {source_id}")
            
        except Exception as e:
            logger.error(f"Error reindexing source: {str(e)}")
            raise

