"""
Reindexing Background Tasks

Uses FastAPI BackgroundTasks for async reindexing operations
"""

from sqlalchemy.orm import Session
from app.db.models.knowledge_base import KnowledgeSource, SourceStatus, SourceType
from app.services.knowledge_service import KnowledgeService
from app.services.background_tasks import safe_background_task
import logging
import asyncio

logger = logging.getLogger(__name__)


@safe_background_task
def reindex_source_task(
    source_id: str,
    organization_id: str,
    db: Session
):
    """
    Reindex a knowledge source in background.
    
    Args:
        source_id: Source ID to reindex
        organization_id: Organization ID
        db: Database session
    """
    try:
        logger.info(f"Starting reindex for source {source_id}")
        
        # Get source
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id
        ).first()
        
        if not source:
            logger.error(f"Source {source_id} not found")
            return {"success": False, "error": "Source not found"}
        
        # Update status to processing
        source.status = SourceStatus.PROCESSING
        db.commit()
        
        # Create knowledge service and reindex
        knowledge_service = KnowledgeService(db)
        
        # Run async method in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                knowledge_service.reindex_source(source_id, organization_id)
            )
        finally:
            loop.close()
        
        logger.info(f"Source {source_id} reindexed successfully")
        
        return {
            "success": True,
            "source_id": source_id
        }
        
    except Exception as e:
        logger.error(f"Failed to reindex source {source_id}: {str(e)}")
        
        # Update source status to failed
        try:
            if 'source' in locals() and source:
                source.status = SourceStatus.FAILED
                source.error_message = str(e)
                db.commit()
        except Exception as commit_error:
            logger.error(f"Error updating failed status: {str(commit_error)}")
            db.rollback()
        
        raise
