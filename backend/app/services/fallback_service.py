"""
Fallback Service

Handles fallback responses when the bot can't provide a confident answer:
- Confidence threshold checking
- Fallback response management
- Escalation to human support
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models.bot import Bot
from app.schemas.bot import FallbackResponse, FallbackResponsesUpdate
from app.core.exceptions import NotFoundException, ValidationException, ServiceException

logger = logging.getLogger(__name__)


class FallbackService:
    """
    Service for managing fallback responses.
    """
    
    def __init__(self):
        """Initialize fallback service."""
        pass
    
    def get_fallback_responses(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get fallback responses for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            List of fallback responses
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get fallback responses from settings
        settings = bot.settings or {}
        fallback_responses = settings.get("fallback_responses", [])
        
        # Format responses
        formatted_responses = []
        for i, response in enumerate(fallback_responses):
            if isinstance(response, dict):
                formatted_responses.append({
                    "id": response.get("id", str(uuid.uuid4())),
                    "message": response.get("message", ""),
                    "condition": response.get("condition", "low_confidence"),
                    "action": response.get("action")
                })
            else:
                # Handle string fallbacks (legacy)
                formatted_responses.append({
                    "id": str(uuid.uuid4()),
                    "message": response,
                    "condition": "low_confidence",
                    "action": None
                })
        
        # If no fallback responses are configured, return default
        if not formatted_responses:
            formatted_responses = [
                {
                    "id": str(uuid.uuid4()),
                    "message": "I'm not sure about that. Could you please rephrase your question?",
                    "condition": "low_confidence",
                    "action": None
                }
            ]
        
        return formatted_responses
    
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
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Initialize settings if not present
        if not bot.settings:
            bot.settings = {}
        
        # Update fallback responses
        responses = [r.model_dump() for r in responses_data.responses]
        
        # Ensure each response has an ID
        for response in responses:
            if "id" not in response:
                response["id"] = str(uuid.uuid4())
        
        bot.settings["fallback_responses"] = responses
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Fallback responses updated for bot: {bot_id}")
        return bot
    
    def add_fallback_response(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        response: FallbackResponse
    ) -> Dict[str, Any]:
        """
        Add a single fallback response.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            response: Fallback response to add
            
        Returns:
            Added response with ID
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Initialize settings if not present
        if not bot.settings:
            bot.settings = {}
        
        # Initialize fallback responses if not present
        if "fallback_responses" not in bot.settings:
            bot.settings["fallback_responses"] = []
        
        # Create response object
        response_dict = response.dict()
        response_dict["id"] = str(uuid.uuid4())
        
        # Add response
        bot.settings["fallback_responses"].append(response_dict)
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Added fallback response for bot: {bot_id}")
        return response_dict
    
    def delete_fallback_response(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        response_id: str
    ) -> Dict[str, Any]:
        """
        Delete a fallback response.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            response_id: Response ID to delete
            
        Returns:
            Success message
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Check if bot has fallback responses
        if not bot.settings or "fallback_responses" not in bot.settings:
            raise NotFoundException(f"No fallback responses found for bot {bot_id}")
        
        # Find response by ID
        responses = bot.settings["fallback_responses"]
        response_index = None
        for i, r in enumerate(responses):
            if isinstance(r, dict) and r.get("id") == response_id:
                response_index = i
                break
        
        if response_index is None:
            raise NotFoundException(f"Fallback response with ID {response_id} not found")
        
        # Remove response
        removed_response = responses.pop(response_index)
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Deleted fallback response {response_id} for bot: {bot_id}")
        return {
            "success": True,
            "message": f"Fallback response deleted successfully",
            "deleted_response": removed_response
        }
    
    def check_confidence_and_get_fallback(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        confidence_score: float,
        query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if confidence is below threshold and get appropriate fallback.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID
            confidence_score: Confidence score (0-1)
            query: User query
            
        Returns:
            Fallback response if confidence is low, None otherwise
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get confidence threshold from settings
        settings = bot.settings or {}
        threshold = settings.get("confidence_threshold", 0.7)
        
        # If confidence is above threshold, no fallback needed
        if confidence_score >= threshold:
            return None
        
        # Get fallback responses
        fallback_responses = self.get_fallback_responses(db, bot_id, organization_id)
        
        # Find appropriate fallback response based on condition
        # For now, just use the first one with condition "low_confidence"
        for response in fallback_responses:
            if response.get("condition") == "low_confidence":
                return {
                    "message": response.get("message"),
                    "action": response.get("action"),
                    "confidence_score": confidence_score,
                    "threshold": threshold,
                    "query": query
                }
        
        # If no specific fallback found, use default
        return {
            "message": "I'm not sure about that. Could you please rephrase your question?",
            "action": None,
            "confidence_score": confidence_score,
            "threshold": threshold,
            "query": query
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_fallback_service = None


def get_fallback_service() -> FallbackService:
    """
    Get the global fallback service instance.
    
    Returns:
        FallbackService: Global instance
    """
    global _fallback_service
    
    if _fallback_service is None:
        _fallback_service = FallbackService()
    
    return _fallback_service
