"""
Document Processing Background Tasks

Uses FastAPI BackgroundTasks for async processing
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models.knowledge_base import Document, KnowledgeSource
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import QdrantService
from app.services.background_tasks import safe_background_task
from app.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)


@safe_background_task
def process_document_task(
    document_id: str,
    bot_id: str,
    organization_id: str,
    db: Session
):
    """
    Process uploaded document in background.
    
    Args:
        document_id: Document ID
        bot_id: Bot ID
        organization_id: Organization ID
        db: Database session
    """
    try:
        logger.info(f"Processing document {document_id}")
        
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"success": False, "error": "Document not found"}
        
        # Get source
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == document.source_id
        ).first()
        
        if not source:
            logger.error(f"Source for document {document_id} not found")
            return {"success": False, "error": "Source not found"}
        
        # Update status
        document.processing_status = "processing"
        source.status = "processing"
        db.commit()
        
        # Get services (singleton pattern ensures model is loaded only once)
        doc_processor = DocumentProcessor()
        embedding_service = get_embedding_service()  # Reuses existing instance
        qdrant_service = QdrantService()
        
        # Process document
        result = doc_processor.process_document(
            file_path=document.file_path,
            source_metadata={
                "document_id": document_id,
                "document_name": document.filename,
                "bot_id": bot_id,
                "organization_id": organization_id
            }
        )
        
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error"))
        
        chunks_data = result.get("chunks", [])
        
        if not chunks_data:
            raise Exception("No chunks generated from document")
        
        # Generate embeddings
        chunk_texts = [chunk["content"] for chunk in chunks_data]
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
        
        # Prepare payloads and IDs
        payloads = []
        ids = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks_data, embeddings)):
            chunk_id = str(uuid.uuid4())
            
            payload = {
                "chunk_id": chunk_id,
                "source_id": document.source_id,
                "bot_id": bot_id,
                "organization_id": organization_id,
                "document_id": document_id,
                "source_type": "document",
                "content": chunk["content"],
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "metadata": chunk.get("metadata", {})
            }
            
            payloads.append(payload)
            ids.append(chunk_id)
        
        # Insert vectors into Qdrant
        qdrant_service.insert_vectors(
            collection_name=collection_name,
            vectors=embeddings,
            payloads=payloads,
            ids=ids
        )
        
        # Update document and source status
        document.processing_status = "completed"
        source.status = "indexed"
        source.chunk_count = len(chunks_data)
        source.last_indexed_at = datetime.utcnow().isoformat()
        db.commit()
        
        logger.info(f"Document {document_id} processed successfully: {len(chunks_data)} chunks")
        
        return {
            "success": True,
            "document_id": document_id,
            "chunks_created": len(chunks_data)
        }
        
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {str(e)}")
        
        # Update document and source status
        try:
            if 'document' in locals() and document:
                document.processing_status = "failed"
                document.error_message = str(e)
            if 'source' in locals() and source:
                source.status = "failed"
                source.error_message = str(e)
            db.commit()
        except Exception as commit_error:
            logger.error(f"Error updating failed status: {str(commit_error)}")
            db.rollback()
        
        raise


@safe_background_task
def cleanup_failed_documents_task(db: Session):
    """
    Cleanup failed document processing attempts.
    
    Args:
        db: Database session
    """
    try:
        # Find documents stuck in processing for > 1 hour
        threshold = datetime.utcnow() - timedelta(hours=1)
        
        stuck_docs = db.query(Document).filter(
            Document.processing_status == "processing",
            Document.updated_at < threshold
        ).all()
        
        for doc in stuck_docs:
            doc.processing_status = "failed"
            doc.error_message = "Processing timeout"
        
        db.commit()
        
        logger.info(f"Cleaned up {len(stuck_docs)} stuck documents")
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        raise
