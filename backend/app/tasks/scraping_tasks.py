"""
Web Scraping Background Tasks

Uses FastAPI BackgroundTasks for async processing
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.knowledge_base import WebPage, KnowledgeSource
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import QdrantService
from app.services.background_tasks import safe_background_task
from app.config import settings
import logging
import uuid
import asyncio

logger = logging.getLogger(__name__)


@safe_background_task
def scrape_website_task(
    source_id: str,
    url: str,
    bot_id: str,
    organization_id: str,
    max_pages: int,
    db: Session
):
    """
    Scrape website in background.
    
    Args:
        source_id: Knowledge source ID
        url: Website URL to scrape
        bot_id: Bot ID
        organization_id: Organization ID
        max_pages: Maximum pages to scrape
        db: Database session
    """
    loop = None
    try:
        logger.info(f"Scraping website: {url}")
        
        # Get source
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id
        ).first()
        
        if not source:
            logger.error(f"Source {source_id} not found")
            return {"success": False, "error": "Source not found"}
        
        # Update status
        source.status = "processing"
        db.commit()
        
        # Get services (singleton pattern ensures model is loaded only once)
        from app.services.scraper_service import get_web_scraper
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get singleton scraper instance (reuses existing instance)
        scraper = loop.run_until_complete(
            get_web_scraper(max_pages=max_pages, follow_links=True)
        )
        doc_processor = DocumentProcessor()
        embedding_service = get_embedding_service()  # Reuses existing instance
        qdrant_service = QdrantService()
        
        # Scrape website (async)
        scrape_result = loop.run_until_complete(
            scraper.scrape_website(url, use_sitemap=True)
        )
        
        pages = scrape_result.get("pages", [])
        
        if not pages:
            raise Exception("No pages scraped")
        
        # Process each page
        total_chunks = 0
        all_payloads = []
        all_embeddings = []
        all_ids = []
        
        for page_data in pages:
            # Create WebPage record
            webpage = WebPage(
                id=str(uuid.uuid4()),
                source_id=source_id,
                url=page_data["url"],
                title=page_data.get("title", ""),
                content=page_data["content"],
                scraped_at=page_data.get("scraped_at", datetime.utcnow().isoformat()),
                status_code=page_data.get("status_code", 200),
                is_indexed=False
            )
            db.add(webpage)
            db.flush()
            
            # Chunk content
            chunks = doc_processor.chunk_text(
                text=page_data["content"],
                metadata={
                    "source_id": source_id,
                    "webpage_id": str(webpage.id),
                    "url": page_data["url"],
                    "title": page_data.get("title", ""),
                    "bot_id": bot_id,
                    "organization_id": organization_id,
                    "source_type": "web"
                }
            )
            
            # Generate embeddings for this page's chunks
            chunk_texts = [chunk["content"] for chunk in chunks]
            embeddings = embedding_service.generate_embeddings(chunk_texts)
            
            # Prepare data for Qdrant
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid.uuid4())
                
                payload = {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "bot_id": bot_id,
                    "organization_id": organization_id,
                    "webpage_id": str(webpage.id),
                    "source_type": "web",
                    "content": chunk["content"],
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": chunk.get("metadata", {})
                }
                
                all_payloads.append(payload)
                all_embeddings.append(embedding)
                all_ids.append(chunk_id)
            
            webpage.is_indexed = True
            total_chunks += len(chunks)
        
        # Index all chunks in Qdrant
        collection_name = f"bot_{bot_id}"
        
        # Ensure collection exists with text index
        if not qdrant_service.collection_exists(collection_name):
            qdrant_service.create_collection_with_text_index(
                collection_name=collection_name,
                vector_size=settings.EMBEDDING_DIMENSION,
                distance="Cosine"
            )
        
        # Insert vectors
        if all_embeddings:
            qdrant_service.insert_vectors(
                collection_name=collection_name,
                vectors=all_embeddings,
                payloads=all_payloads,
                ids=all_ids
            )
        
        # Update source status
        source.status = "indexed"
        source.last_indexed_at = datetime.utcnow().isoformat()
        source.chunk_count = total_chunks
        db.commit()
        
        logger.info(f"Website scraped successfully: {len(pages)} pages, {total_chunks} chunks")
        
        return {
            "success": True,
            "source_id": source_id,
            "pages_scraped": len(pages),
            "chunks_created": total_chunks
        }
        
    except Exception as e:
        logger.error(f"Failed to scrape website {url}: {str(e)}")
        
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
    finally:
        # Clean up event loop
        if loop is not None:
            try:
                loop.close()
            except Exception as loop_error:
                logger.warning(f"Error closing event loop: {str(loop_error)}")
