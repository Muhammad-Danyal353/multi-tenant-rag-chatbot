"""
Knowledge Base Schemas

Pydantic schemas for knowledge base operations including:
- Document upload and processing
- Web scraping
- Text content management
- Source management
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SourceType(str, Enum):
    """Type of knowledge source"""
    DOCUMENT = "document"
    WEB = "web"
    TEXT = "text"


class SourceStatus(str, Enum):
    """Status of knowledge source processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    PAUSED = "paused"


class DocumentType(str, Enum):
    """Supported document types"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


# ============================================================================
# DOCUMENT UPLOAD SCHEMAS
# ============================================================================

class DocumentUploadResponse(BaseModel):
    """Response for document upload"""
    id: str
    source_id: str
    filename: str
    file_size: int
    file_type: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentMetadata(BaseModel):
    """Document metadata"""
    filename: str
    file_size: int
    file_type: str
    page_count: Optional[int] = None
    uploaded_by: str
    uploaded_at: datetime


# ============================================================================
# WEB SCRAPING SCHEMAS
# ============================================================================

class WebScrapeRequest(BaseModel):
    """Request to scrape a website"""
    url: HttpUrl = Field(..., description="URL to scrape")
    bot_id: str = Field(..., description="Bot ID to associate with")
    max_pages: int = Field(default=10, ge=1, le=100, description="Maximum pages to scrape")
    follow_links: bool = Field(default=True, description="Whether to follow links")
    include_sitemap: bool = Field(default=True, description="Whether to use sitemap")
    
    @validator('url')
    def validate_url(cls, v):
        """Validate URL is accessible"""
        if not str(v).startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class WebScrapeResponse(BaseModel):
    """Response for web scraping request"""
    source_id: str
    url: str
    status: str
    pages_queued: int
    estimated_time: Optional[int] = None  # seconds
    message: str


class WebPageData(BaseModel):
    """Individual web page data"""
    id: str
    url: str
    title: Optional[str]
    content: str
    status_code: int
    scraped_at: datetime
    is_indexed: bool
    
    class Config:
        from_attributes = True


# ============================================================================
# TEXT CONTENT SCHEMAS
# ============================================================================

class TextContentCreate(BaseModel):
    """Create text content"""
    bot_id: str = Field(..., description="Bot ID to associate with")
    title: str = Field(..., min_length=1, max_length=255, description="Content title")
    content: str = Field(..., min_length=1, description="Text content")
    category: Optional[str] = Field(None, max_length=100, description="Content category")
    tags: List[str] = Field(default_factory=list, description="Content tags")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Limit number of tags"""
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v


class TextContentUpdate(BaseModel):
    """Update text content"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        """Limit number of tags"""
        if v and len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v


class TextContentResponse(BaseModel):
    """Text content response"""
    id: str
    source_id: str
    title: str
    content: str
    category: Optional[str]
    tags: List[str]
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]
    chunk_count: Optional[int] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# KNOWLEDGE SOURCE SCHEMAS
# ============================================================================

class KnowledgeSourceBase(BaseModel):
    """Base knowledge source schema"""
    name: str
    source_type: SourceType
    status: SourceStatus


class KnowledgeSourceCreate(BaseModel):
    """Create knowledge source"""
    bot_id: str
    name: str
    source_type: SourceType
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    """Update knowledge source - supports all source types"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Source name")
    # For web sources
    url: Optional[HttpUrl] = Field(None, description="Website URL (web sources only)")
    # For text sources
    content: Optional[str] = Field(None, min_length=1, description="Text content (text sources only)")
    # Common metadata for all types
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")
    
    @ validator('url')
    def validate_url(cls, v):
        """Validate URL format"""
        if v and not str(v).startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class KnowledgeSourceResponse(BaseModel):
    """Knowledge source response"""
    id: str
    bot_id: str
    name: str
    source_type: SourceType
    status: SourceStatus
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    last_indexed_at: Optional[datetime]
    
    # Counts
    document_count: Optional[int] = 0
    webpage_count: Optional[int] = 0
    chunk_count: Optional[int] = 0
    
    class Config:
        from_attributes = True



class KnowledgeSourceList(BaseModel):
    """List of knowledge sources"""
    sources: List[KnowledgeSourceResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# CHUNK SCHEMAS
# ============================================================================

class ChunkCreate(BaseModel):
    """Create chunk"""
    source_id: str
    bot_id: str
    organization_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChunkResponse(BaseModel):
    """Chunk response"""
    id: str
    source_id: str
    bot_id: str
    content: str
    chunk_index: int
    embedding_id: Optional[str]
    metadata: Dict[str, Any]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# PROCESSING STATUS SCHEMAS
# ============================================================================

class ProcessingStatus(BaseModel):
    """Processing status for async operations"""
    source_id: str
    status: SourceStatus
    progress: int = Field(ge=0, le=100, description="Progress percentage")
    total_items: int
    processed_items: int
    failed_items: int
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class ReindexRequest(BaseModel):
    """Request to reindex a source"""
    source_id: str
    force: bool = Field(default=False, description="Force reindex even if already indexed")


class ReindexResponse(BaseModel):
    """Response for reindex request"""
    source_id: str
    status: str
    message: str
    chunks_created: Optional[int] = None


# ============================================================================
# BULK OPERATIONS SCHEMAS
# ============================================================================

class BulkDeleteRequest(BaseModel):
    """Bulk delete sources"""
    source_ids: List[str] = Field(..., min_items=1, max_items=50)


class BulkDeleteResponse(BaseModel):
    """Bulk delete response"""
    deleted_count: int
    failed_ids: List[str] = Field(default_factory=list)
    message: str


# ============================================================================
# SEARCH & RETRIEVAL SCHEMAS
# ============================================================================

class SourceSearchRequest(BaseModel):
    """Search knowledge sources"""
    query: Optional[str] = None
    source_type: Optional[SourceType] = None
    status: Optional[SourceStatus] = None
    bot_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================

class KnowledgeBaseStats(BaseModel):
    """Knowledge base statistics"""
    total_sources: int
    total_documents: int
    total_webpages: int
    total_text_contents: int
    total_chunks: int
    total_size_bytes: int
    indexed_sources: int
    pending_sources: int
    failed_sources: int
    last_updated: datetime

