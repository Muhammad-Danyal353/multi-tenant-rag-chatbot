"""
Text Content Processing Background Tasks

Uses FastAPI BackgroundTasks for async processing
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.knowledge_base import TextContent, KnowledgeSource, Chunk
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import QdrantService
from app.services.background_tasks import safe_background_task
from app.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)


@safe_background_task
def process_text_content_task(
    text_content_id: str,
    source_id: str,
    bot_id: str,
    organization_id: str,
    db: Session
):
    """
    Process text content in background.
    
    Args:
        text_content_id: Text content ID
        source_id: Source ID
        bot_id: Bot ID
        organization_id: Organization ID
        db: Database session
    """
    try:
        logger.info(f"Processing text content {text_content_id}")
        
        # Get text content and source
        text_content = db.query(TextContent).filter(
            TextContent.id == text_content_id
        ).first()
        
        if not text_content:
            logger.error(f"Text content {text_content_id} not found")
            return {"success": False, "error": "Text content not found"}
        
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id
        ).first()
        
        if not source:
            logger.error(f"Source {source_id} not found")
            return {"success": False, "error": "Source not found"}
        
        # Update status to processing
        source.status = "processing"
        db.commit()
        
        # Get services
        doc_processor = DocumentProcessor()
        embedding_service = get_embedding_service()
        qdrant_service = QdrantService()
        
        # Chunk the text content
        chunks = doc_processor.chunk_text(
            text=text_content.content,
            metadata={
                "source_id": source_id,
                "text_content_id": text_content_id,
                "title": text_content.title,
                "category": text_content.category,
                "tags": text_content.tags,
                "bot_id": bot_id,
                "organization_id": organization_id,
                "source_type": "text"
            }
        )
        
        if not chunks:
            raise Exception("No chunks generated from text content")
        
        # Generate embeddings
        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = embedding_service.generate_embeddings(chunk_texts)
        
        # Prepare data for Qdrant
        collection_name = f"bot_{bot_id}"
        
        # Ensure collection exists with text index
        if not qdrant_service.collection_exists(collection_name):
            qdrant_service.create_collection_with_text_index(
                collection_name=collection_name,
                vector_size=settings.EMBEDDING_DIMENSION,
                distance="Cosine"
            )
        
        # Prepare payloads and IDs for Qdrant
        payloads = []
        ids = []
        db_chunks = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            
            # Prepare payload
            payload = {
                "chunk_id": chunk_id,
                "source_id": source_id,
                "bot_id": bot_id,
                "organization_id": organization_id,
                "text_content_id": text_content_id,
                "source_type": "text",
                "content": chunk["content"],
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "metadata": chunk.get("metadata", {})
            }
            
            payloads.append(payload)
            ids.append(chunk_id)
            
            # Create database chunk
            db_chunk = Chunk(
                id=chunk_id,
                source_id=source_id,
                bot_id=bot_id,
                organization_id=organization_id,
                content=chunk["content"],
                chunk_index=chunk["chunk_index"],
                meta_data=chunk.get("metadata", {}),
                is_active=True
            )
            db_chunks.append(db_chunk)
        
        # Save chunks to database
        db.bulk_save_objects(db_chunks)
        db.commit()
        
        # Insert vectors into Qdrant
        qdrant_service.insert_vectors(
            collection_name=collection_name,
            vectors=embeddings,
            payloads=payloads,
            ids=ids
        )
        
        # Update source status
        source.status = "indexed"
        source.chunk_count = len(chunks)
        source.last_indexed_at = datetime.utcnow().isoformat()
        db.commit()
        
        logger.info(f"Text content processed successfully: {len(chunks)} chunks")
        
        return {
            "success": True,
            "text_content_id": text_content_id,
            "chunks_created": len(chunks)
        }
        
    except Exception as e:
        logger.error(f"Failed to process text content {text_content_id}: {str(e)}")
        
        # Update source status to failed
        try:
            if 'source' in locals() and source:
                source.status = "failed"
                source.error_message = str(e)
                db.commit()
        except Exception as commit_error:
            logger.error(f"Error updating failed status: {str(commit_error)}")
            db.rollback()
        
        raise
