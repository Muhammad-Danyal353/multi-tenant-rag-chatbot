"""
Template Service

Handles bot templates:
- CRUD operations for templates
- Creating bots from templates
- Template categories and filtering
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from datetime import datetime

from app.db.models.bot_template import BotTemplate
from app.db.models.bot import Bot, BotStatus
from app.schemas.bot import BotTemplateCreate, BotFromTemplateCreate
from app.core.exceptions import NotFoundException, ValidationException, ServiceException

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Service for managing bot templates.
    """
    
    def __init__(self):
        """Initialize template service."""
        pass
    
    def create_template(
        self,
        db: Session,
        template_data: BotTemplateCreate
    ) -> BotTemplate:
        """
        Create a new bot template.
        
        Args:
            db: Database session
            template_data: Template creation data
            
        Returns:
            Newly created BotTemplate
        """
        try:
            # Create new template
            new_template = BotTemplate(
                id=str(uuid.uuid4()),
                name=template_data.name,
                description=template_data.description,
                category=template_data.category,
                settings=template_data.settings,
                widget_settings=template_data.widget_settings,
                system_prompt=template_data.system_prompt,
                suggested_questions=template_data.suggested_questions,
                is_featured=False,
                is_public=True
            )
            
            # Add to database
            db.add(new_template)
            db.commit()
            db.refresh(new_template)
            
            logger.info(f"Template created: {new_template.id}")
            return new_template
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create template: {str(e)}")
            raise ServiceException(f"Failed to create template: {str(e)}")
    
    def get_template(
        self,
        db: Session,
        template_id: str
    ) -> BotTemplate:
        """
        Get template by ID.
        
        Args:
            db: Database session
            template_id: Template ID
            
        Returns:
            BotTemplate object
        """
        template = db.query(BotTemplate).filter(
            BotTemplate.id == template_id
        ).first()
        
        if not template:
            raise NotFoundException(f"Template with ID {template_id} not found")
        
        return template
    
    def list_templates(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured_only: bool = False
    ) -> Tuple[List[BotTemplate], int]:
        """
        List bot templates.
        
        Args:
            db: Database session
            limit: Maximum number of results
            offset: Offset for pagination
            category: Filter by category
            search: Search term for name/description
            featured_only: Only show featured templates
            
        Returns:
            Tuple of (templates list, total count)
        """
        # Base query
        query = db.query(BotTemplate).filter(
            BotTemplate.is_public == True
        )
        
        # Apply filters
        if category:
            query = query.filter(BotTemplate.category == category)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    BotTemplate.name.ilike(search_term),
                    BotTemplate.description.ilike(search_term)
                )
            )
        
        if featured_only:
            query = query.filter(BotTemplate.is_featured == True)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        templates = query.order_by(desc(BotTemplate.is_featured), BotTemplate.name).offset(offset).limit(limit).all()
        
        return templates, total
    
    def update_template(
        self,
        db: Session,
        template_id: str,
        template_data: Dict[str, Any]
    ) -> BotTemplate:
        """
        Update template information.
        
        Args:
            db: Database session
            template_id: Template ID
            template_data: Template update data
            
        Returns:
            Updated BotTemplate
        """
        # Get template
        template = self.get_template(db, template_id)
        
        # Update fields if provided
        if "name" in template_data:
            template.name = template_data["name"]
        
        if "description" in template_data:
            template.description = template_data["description"]
        
        if "category" in template_data:
            template.category = template_data["category"]
        
        if "settings" in template_data:
            template.settings = template_data["settings"]
        
        if "widget_settings" in template_data:
            template.widget_settings = template_data["widget_settings"]
        
        if "system_prompt" in template_data:
            template.system_prompt = template_data["system_prompt"]
        
        if "suggested_questions" in template_data:
            template.suggested_questions = template_data["suggested_questions"]
        
        if "is_featured" in template_data:
            template.is_featured = template_data["is_featured"]
        
        if "is_public" in template_data:
            template.is_public = template_data["is_public"]
        
        # Save changes
        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
        
        logger.info(f"Template updated: {template_id}")
        return template
    
    def delete_template(
        self,
        db: Session,
        template_id: str
    ) -> Dict[str, Any]:
        """
        Delete a template.
        
        Args:
            db: Database session
            template_id: Template ID
            
        Returns:
            Success message
        """
        # Get template
        template = self.get_template(db, template_id)
        
        try:
            # Delete template from database
            db.delete(template)
            db.commit()
            
            logger.info(f"Template deleted: {template_id}")
            return {"success": True, "message": f"Template {template_id} deleted successfully"}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete template: {str(e)}")
            raise ServiceException(f"Failed to delete template: {str(e)}")
    
    def create_bot_from_template(
        self,
        db: Session,
        organization_id: str,
        user_id: str,
        template_data: BotFromTemplateCreate
    ) -> Bot:
        """
        Create a bot from a template.
        
        Args:
            db: Database session
            organization_id: Organization ID
            user_id: User ID creating the bot
            template_data: Template creation data
            
        Returns:
            Newly created Bot
        """
        try:
            # Get template
            template = self.get_template(db, template_data.template_id)
            
            # Create bot from template
            from app.services.bot_service import get_bot_service
            bot_service = get_bot_service()
            
            # Create bot data
            from app.schemas.bot import BotCreate
            bot_data = BotCreate(
                name=template_data.name,
                description=template_data.description or template.description,
                status=BotStatus.DRAFT,
                settings=template.settings,
                widget_settings=template.widget_settings
            )
            
            # Create bot
            bot = bot_service.create_bot(
                db=db,
                organization_id=organization_id,
                user_id=user_id,
                bot_data=bot_data
            )
            
            logger.info(f"Bot created from template: {template.id} → {bot.id}")
            return bot
            
        except Exception as e:
            logger.error(f"Failed to create bot from template: {str(e)}")
            raise ServiceException(f"Failed to create bot from template: {str(e)}")
    
    def get_template_categories(
        self,
        db: Session
    ) -> List[Dict[str, Any]]:
        """
        Get list of template categories with counts.
        
        Args:
            db: Database session
            
        Returns:
            List of categories with counts
        """
        # Get distinct categories with counts
        categories = db.query(
            BotTemplate.category,
            func.count(BotTemplate.id).label("count")
        ).filter(
            BotTemplate.is_public == True
        ).group_by(
            BotTemplate.category
        ).order_by(
            BotTemplate.category
        ).all()
        
        # Format result
        return [
            {"category": category, "count": count}
            for category, count in categories
        ]
    
    def get_featured_templates(
        self,
        db: Session,
        limit: int = 5
    ) -> List[BotTemplate]:
        """
        Get featured templates.
        
        Args:
            db: Database session
            limit: Maximum number of results
            
        Returns:
            List of featured templates
        """
        # Get featured templates
        templates = db.query(BotTemplate).filter(
            BotTemplate.is_public == True,
            BotTemplate.is_featured == True
        ).order_by(
            BotTemplate.name
        ).limit(limit).all()
        
        return templates


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_template_service = None


def get_template_service() -> TemplateService:
    """
    Get the global template service instance.
    
    Returns:
        TemplateService: Global instance
    """
    global _template_service
    
    if _template_service is None:
        _template_service = TemplateService()
    
    return _template_service
