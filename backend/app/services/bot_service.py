"""
Bot Service

Handles bot management operations:
- CRUD operations for bots
- API key generation and validation
- Bot templates
- Widget customization
- Suggested questions
- Fallback responses
"""

import logging
import uuid
import secrets
import string
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.db.models.bot import Bot, BotStatus
from app.db.models.conversation import Conversation, Message
from app.db.models.knowledge_base import KnowledgeSource, Chunk
from app.schemas.bot import (
    BotCreate, BotUpdate, BotSettingsUpdate, WidgetSettingsUpdate,
    SuggestedQuestionsUpdate, FallbackResponsesUpdate, BotCloneRequest
)
from app.core.exceptions import (
    NotFoundException, ValidationException, DuplicateException, 
    UnauthorizedException, ServiceException
)
from app.core.security import hash_api_key, verify_api_key
from app.services.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)


class BotService:
    """
    Service for managing bots.
    """
    
    def __init__(self):
        """Initialize bot service."""
        self.qdrant_service = get_qdrant_service()
    
    def create_bot(
        self,
        db: Session,
        organization_id: str,
        user_id: str,
        bot_data: BotCreate
    ) -> Bot:
        """
        Create a new bot.
        
        Args:
            db: Database session
            organization_id: Organization ID
            user_id: User ID creating the bot
            bot_data: Bot creation data
            
        Returns:
            Newly created Bot
        """
        try:
            # Check if organization has reached bot limit
            # This would be implemented with subscription/plan limits
            
            # Create new bot
            new_bot = Bot(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                created_by=user_id,
                name=bot_data.name,
                description=bot_data.description,
                avatar_url=str(bot_data.avatar_url) if bot_data.avatar_url else None,
                status=bot_data.status,
                settings=bot_data.settings or {},
                widget_settings=bot_data.widget_settings or {},
                allowed_domains=bot_data.allowed_domains or []
            )
            
            # Generate API key
            api_key = self._generate_api_key()
            new_bot.api_key = api_key
            new_bot.api_key_hash = hash_api_key(api_key)
            
            # Add to database
            db.add(new_bot)
            db.commit()
            db.refresh(new_bot)
            
            # Create Qdrant collection for this bot
            self._create_bot_collection(new_bot.id)
            
            logger.info(f"Bot created: {new_bot.id} (org: {organization_id})")
            return new_bot
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create bot: {str(e)}")
            raise ServiceException(f"Failed to create bot: {str(e)}")
    
    def get_bot(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> Bot:
        """
        Get bot by ID.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            Bot object
        """
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        return bot
    
    def get_bot_detail(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed bot information including statistics.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            Bot details with statistics
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Get knowledge source count
        knowledge_source_count = db.query(func.count(KnowledgeSource.id)).filter(
            KnowledgeSource.bot_id == bot_id
        ).scalar() or 0
        
        # Get conversation count
        conversation_count = db.query(func.count(Conversation.id)).filter(
            Conversation.bot_id == bot_id
        ).scalar() or 0
        
        # Get total messages
        total_messages = db.query(func.count(Message.id)).join(
            Conversation, Message.conversation_id == Conversation.id
        ).filter(
            Conversation.bot_id == bot_id
        ).scalar() or 0
        
        # Get average rating
        average_rating = db.query(func.avg(Conversation.rating)).filter(
            Conversation.bot_id == bot_id,
            Conversation.rating.isnot(None)
        ).scalar()
        
        # Combine data
        bot_dict = bot.to_dict()
        bot_dict.update({
            "knowledge_source_count": knowledge_source_count,
            "conversation_count": conversation_count,
            "total_messages": total_messages,
            "average_rating": float(average_rating) if average_rating else None
        })
        
        return bot_dict
    
    def list_bots(
        self,
        db: Session,
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Bot], int]:
        """
        List bots for an organization.
        
        Args:
            db: Database session
            organization_id: Organization ID
            limit: Maximum number of results
            offset: Offset for pagination
            status: Filter by status
            search: Search term for name/description
            
        Returns:
            Tuple of (bots list, total count)
        """
        # Base query
        query = db.query(Bot).filter(
            Bot.organization_id == organization_id
        )
        
        # Apply filters
        if status:
            query = query.filter(Bot.status == status)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Bot.name.ilike(search_term),
                    Bot.description.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        bots = query.order_by(desc(Bot.updated_at)).offset(offset).limit(limit).all()
        
        return bots, total
    
    def update_bot(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        bot_data: BotUpdate
    ) -> Bot:
        """
        Update bot information.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            bot_data: Bot update data
            
        Returns:
            Updated Bot
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Update fields if provided
        if bot_data.name is not None:
            bot.name = bot_data.name
        
        if bot_data.description is not None:
            bot.description = bot_data.description
        
        if bot_data.avatar_url is not None:
            bot.avatar_url = str(bot_data.avatar_url)
        
        if bot_data.status is not None:
            bot.status = bot_data.status
        
        if bot_data.settings is not None:
            bot.settings = bot_data.settings
        
        if bot_data.widget_settings is not None:
            bot.widget_settings = bot_data.widget_settings
        
        if bot_data.allowed_domains is not None:
            bot.allowed_domains = bot_data.allowed_domains
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Bot updated: {bot_id}")
        return bot
    
    def update_bot_settings(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        settings_data: BotSettingsUpdate
    ) -> Bot:
        """
        Update bot behavior settings.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            settings_data: Settings update data
            
        Returns:
            Updated Bot
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Initialize settings if not present
        if not bot.settings:
            bot.settings = {}
        
        # Update settings fields if provided
        settings_dict = settings_data.model_dump(exclude_unset=True)
        for key, value in settings_dict.items():
            bot.settings[key] = value
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Bot settings updated: {bot_id}")
        return bot
    
    def update_widget_settings(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        widget_data: WidgetSettingsUpdate
    ) -> Bot:
        """
        Update widget appearance settings.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            widget_data: Widget settings update data
            
        Returns:
            Updated Bot
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Initialize widget settings if not present
        if not bot.widget_settings:
            bot.widget_settings = {}
        
        # Update widget settings fields if provided
        widget_dict = widget_data.model_dump(exclude_unset=True)
        for key, value in widget_dict.items():
            if key == "colors" and value:
                # Handle nested color object
                if "colors" not in bot.widget_settings:
                    bot.widget_settings["colors"] = {}
                
                for color_key, color_value in value.items():
                    bot.widget_settings["colors"][color_key] = color_value
            else:
                bot.widget_settings[key] = value
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Widget settings updated: {bot_id}")
        return bot
    
    def delete_bot(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Delete a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            Success message
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        try:
            # Delete Qdrant collection
            self._delete_bot_collection(bot_id)
            
            # Delete bot from database
            db.delete(bot)
            db.commit()
            
            logger.info(f"Bot deleted: {bot_id}")
            return {"success": True, "message": f"Bot {bot_id} deleted successfully"}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete bot: {str(e)}")
            raise ServiceException(f"Failed to delete bot: {str(e)}")
    
    def generate_api_key(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> Dict[str, str]:
        """
        Generate a new API key for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            Dictionary with new API key
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Generate new API key
        api_key = self._generate_api_key()
        
        # Update bot
        bot.api_key = api_key
        bot.api_key_hash = hash_api_key(api_key)
        bot.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"API key regenerated for bot: {bot_id}")
        return {"bot_id": bot_id, "api_key": api_key}
    
    def update_suggested_questions(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        questions_data: SuggestedQuestionsUpdate
    ) -> Bot:
        """
        Update suggested questions for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            questions_data: Suggested questions data
            
        Returns:
            Updated Bot
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Initialize widget settings if not present
        if not bot.widget_settings:
            bot.widget_settings = {}
        
        # Update suggested questions
        questions = [q.dict() for q in questions_data.questions]
        bot.widget_settings["suggested_questions"] = questions
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Suggested questions updated for bot: {bot_id}")
        return bot
    
    def update_fallback_responses(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        responses_data: FallbackResponsesUpdate
    ) -> Bot:
        """
        Update fallback responses for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            responses_data: Fallback responses data
            
        Returns:
            Updated Bot
        """
        # Get bot
        bot = self.get_bot(db, bot_id, organization_id)
        
        # Initialize settings if not present
        if not bot.settings:
            bot.settings = {}
        
        # Update fallback responses
        responses = [r.dict() for r in responses_data.responses]
        bot.settings["fallback_responses"] = responses
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Fallback responses updated for bot: {bot_id}")
        return bot
    
    def clone_bot(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        user_id: str,
        clone_data: BotCloneRequest
    ) -> Bot:
        """
        Clone a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID to clone
            organization_id: Organization ID for validation
            user_id: User ID performing the clone
            clone_data: Clone request data
            
        Returns:
            Newly cloned Bot
        """
        # Get source bot
        source_bot = self.get_bot(db, bot_id, organization_id)
        
        try:
            # Create new bot with cloned data
            new_bot = Bot(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                created_by=user_id,
                name=clone_data.name,
                description=source_bot.description,
                avatar_url=source_bot.avatar_url,
                status=BotStatus.DRAFT,  # Always start as draft
                settings=source_bot.settings,
                widget_settings=source_bot.widget_settings,
                allowed_domains=source_bot.allowed_domains
            )
            
            # Generate API key
            api_key = self._generate_api_key()
            new_bot.api_key = api_key
            new_bot.api_key_hash = hash_api_key(api_key)
            
            # Add to database
            db.add(new_bot)
            db.commit()
            db.refresh(new_bot)
            
            # Create Qdrant collection for this bot
            self._create_bot_collection(new_bot.id)
            
            # Clone knowledge base if requested
            if clone_data.clone_knowledge_base:
                self._clone_knowledge_base(db, source_bot.id, new_bot.id, organization_id)
            
            logger.info(f"Bot cloned: {source_bot.id} → {new_bot.id}")
            return new_bot
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to clone bot: {str(e)}")
            raise ServiceException(f"Failed to clone bot: {str(e)}")
    
    def get_bot_by_api_key(
        self,
        db: Session,
        api_key: str
    ) -> Bot:
        """
        Get bot by API key.
        
        Args:
            db: Database session
            api_key: API key
            
        Returns:
            Bot object
        """
        # Get all bots
        bots = db.query(Bot).filter(
            Bot.status == BotStatus.ACTIVE
        ).all()
        
        # Check API key hash
        for bot in bots:
            if bot.api_key_hash and verify_api_key(api_key, bot.api_key_hash):
                return bot
        
        raise NotFoundException("Invalid API key")
    
    def _generate_api_key(self, length: int = 32) -> str:
        """
        Generate a secure API key.
        
        Args:
            length: Length of API key
            
        Returns:
            Secure API key
        """
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(length))
        return f"bot_{api_key}"
    
    def _create_bot_collection(self, bot_id: str) -> None:
        """
        Create Qdrant collection for a bot.
        
        Args:
            bot_id: Bot ID
        """
        collection_name = f"bot_{bot_id}"
        
        try:
            # Create collection with schema
            self.qdrant_service.create_collection(
                collection_name=collection_name,
                create_indexes=True
            )
            
            logger.info(f"Created Qdrant collection for bot: {bot_id}")
            
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {str(e)}")
            raise ServiceException(f"Failed to create vector store: {str(e)}")
    
    def _delete_bot_collection(self, bot_id: str) -> None:
        """
        Delete Qdrant collection for a bot.
        
        Args:
            bot_id: Bot ID
        """
        collection_name = f"bot_{bot_id}"
        
        try:
            # Delete collection
            self.qdrant_service.delete_collection(collection_name)
            logger.info(f"Deleted Qdrant collection for bot: {bot_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {str(e)}")
            # Continue with bot deletion even if collection deletion fails
    
    def _clone_knowledge_base(
        self,
        db: Session,
        source_bot_id: str,
        target_bot_id: str,
        organization_id: str
    ) -> None:
        """
        Clone knowledge base from source bot to target bot.
        
        Args:
            db: Database session
            source_bot_id: Source bot ID
            target_bot_id: Target bot ID
            organization_id: Organization ID
        """
        # This would be implemented to clone knowledge sources
        # For now, just log that this would happen
        logger.info(f"Knowledge base cloning from {source_bot_id} to {target_bot_id} would happen here")
        # In a real implementation, this would:
        # 1. Clone knowledge sources in the database
        # 2. Clone chunks in the database
        # 3. Clone vectors in Qdrant


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_bot_service = None


def get_bot_service() -> BotService:
    """
    Get the global bot service instance.
    
    Returns:
        BotService: Global instance
    """
    global _bot_service
    
    if _bot_service is None:
        _bot_service = BotService()
    
    return _bot_service
