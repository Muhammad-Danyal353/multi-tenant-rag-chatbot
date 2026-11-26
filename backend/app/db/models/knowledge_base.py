"""
Knowledge Base Models

Models for knowledge sources, documents, web pages, text content, and chunks.
"""

from sqlalchemy import Column, String, Integer, Text, JSON, Enum as SQLEnum, ForeignKey, BigInteger, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin
import uuid
import enum


class SourceType(str, enum.Enum):
    """Enumeration of knowledge source types"""
    DOCUMENT = "document"
    WEB = "web"
    TEXT = "text"


class SourceStatus(str, enum.Enum):
    """Enumeration of source processing statuses"""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeSource(Base, TimestampMixin):
    """
    Knowledge source model representing different types of knowledge inputs.
    
    A source can be a document, website, or text content.
    """
    
    __tablename__ = "knowledge_sources"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the knowledge source"
    )
    
    # Foreign Keys
    bot_id = Column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the bot this source belongs to"
    )
    
    # Source Information
    source_type = Column(
        SQLEnum(SourceType),
        nullable=False,
        comment="Type of knowledge source (document, website, text)"
    )
    
    name = Column(
        String(255),
        nullable=False,
        comment="Display name for the source"
    )
    
    status = Column(
        SQLEnum(SourceStatus),
        default=SourceStatus.PENDING,
        nullable=False,
        index=True,
        comment="Processing status of the source"
    )
    
    # Metadata (flexible JSON field)
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata about the source"
    )
    
    # Processing Information
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if processing failed"
    )
    
    last_indexed_at = Column(
        String(100),
        nullable=True,
        comment="Timestamp of last successful indexing"
    )
    
    chunk_count = Column(
        Integer,
        default=0,
        comment="Number of chunks generated from this source"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    bot = relationship("Bot", back_populates="knowledge_sources")
    
    # Specific source type relationships (one-to-one)
    document = relationship(
        "Document",
        back_populates="source",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    webpages = relationship(
        "WebPage",
        back_populates="source",
        cascade="all, delete-orphan"
    )
    
    text_content = relationship(
        "TextContent",
        back_populates="source",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Chunks generated from this source
    chunks = relationship(
        "Chunk",
        back_populates="source",
        cascade="all, delete-orphan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<KnowledgeSource(id={self.id}, name={self.name}, type={self.source_type})>"


class Document(Base, TimestampMixin):
    """
    Document model for uploaded files (PDF, DOCX, TXT, MD).
    """
    
    __tablename__ = "documents"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the document"
    )
    
    # Foreign Keys
    source_id = Column(
        String(36),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to the knowledge source"
    )
    
    # File Information
    filename = Column(
        String(255),
        nullable=False,
        comment="Original filename"
    )
    
    file_path = Column(
        String(500),
        nullable=False,
        comment="Path to the stored file"
    )
    
    file_size = Column(
        BigInteger,
        nullable=False,
        comment="File size in bytes"
    )
    
    file_type = Column(
        String(100),
        nullable=False,
        comment="MIME type of the file"
    )
    
    page_count = Column(
        Integer,
        nullable=True,
        comment="Number of pages (for PDF)"
    )
    
    # Processing Status
    processing_status = Column(
        String(50),
        default="pending",
        comment="Document processing status"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if processing failed"
    )
    
    # Uploader Information
    uploaded_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded this document"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    source = relationship("KnowledgeSource", back_populates="document")
    uploader = relationship("User")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename})>"


class WebPage(Base, TimestampMixin):
    """
    WebPage model for scraped web content.
    """
    
    __tablename__ = "webpages"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the webpage"
    )
    
    # Foreign Keys
    source_id = Column(
        String(36),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the knowledge source"
    )
    
    # Page Information
    url = Column(
        String(2048),
        nullable=False,
        comment="URL of the webpage"
    )
    
    title = Column(
        String(500),
        nullable=True,
        comment="Page title"
    )
    
    content = Column(
        Text,
        nullable=True,
        comment="Extracted text content"
    )
    
    # Scraping Information
    scraped_at = Column(
        String(100),
        nullable=True,
        comment="When the page was scraped"
    )
    
    status_code = Column(
        Integer,
        nullable=True,
        comment="HTTP status code from scraping"
    )
    
    is_indexed = Column(
        Boolean,
        default=False,
        comment="Whether the page has been indexed"
    )
    
    # Metadata
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata (meta tags, etc.)"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    source = relationship("KnowledgeSource", back_populates="webpages")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<WebPage(id={self.id}, url={self.url})>"


class TextContent(Base, TimestampMixin):
    """
    TextContent model for manually entered text snippets.
    """
    
    __tablename__ = "text_contents"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the text content"
    )
    
    # Foreign Keys
    source_id = Column(
        String(36),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to the knowledge source"
    )
    
    # Content
    title = Column(
        String(500),
        nullable=False,
        comment="Title of the text content"
    )
    
    content = Column(
        Text,
        nullable=False,
        comment="The actual text content"
    )
    
    # Organization
    tags = Column(
        JSON,
        nullable=True,
        default=list,
        comment="Tags for organizing content"
    )
    
    category = Column(
        String(100),
        nullable=True,
        comment="Category of the content"
    )
    
    # Creator
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this content"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    source = relationship("KnowledgeSource", back_populates="text_content")
    creator = relationship("User")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<TextContent(id={self.id}, title={self.title})>"


class Chunk(Base, TimestampMixin):
    """
    Chunk model representing text chunks with embeddings.
    
    Chunks are created from knowledge sources and stored in both
    PostgreSQL (for metadata) and Qdrant (for vector search).
    """
    
    __tablename__ = "chunks"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the chunk"
    )
    
    # Foreign Keys
    source_id = Column(
        String(36),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the knowledge source"
    )
    
    bot_id = Column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the bot"
    )
    
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization (for tenant isolation)"
    )
    
    # Chunk Content
    content = Column(
        Text,
        nullable=False,
        comment="The text content of the chunk"
    )
    
    chunk_index = Column(
        Integer,
        nullable=False,
        comment="Index of this chunk within its source"
    )
    
    # Embedding Reference
    embedding_id = Column(
        String(100),
        nullable=True,
        comment="Reference to the embedding in Qdrant"
    )
    
    # Metadata (page number, section, etc.)
    meta_data = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata about the chunk"
    )
    # Example structure:
    # {
    #     "page_number": 5,
    #     "section": "Introduction",
    #     "document_name": "guide.pdf",
    #     "url": "https://example.com/page",
    #     ...
    # }
    
    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this chunk is active for retrieval"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    source = relationship("KnowledgeSource", back_populates="chunks")
    bot = relationship("Bot", back_populates="chunks")
    organization = relationship("Organization")
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, source_id={self.source_id}, index={self.chunk_index})>"
    
    def to_dict(self) -> dict:
        """Convert chunk to dictionary"""
        return {
            "id": self.id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

