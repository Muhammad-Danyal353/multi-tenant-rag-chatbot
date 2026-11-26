"""
Suggested Questions Service

Handles generation and management of suggested questions:
- Automatic generation from knowledge base
- Manual management of suggested questions
- Categorization and ordering of questions
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models.bot import Bot
from app.db.models.knowledge_base import KnowledgeSource, Chunk
from app.schemas.bot import SuggestedQuestion, SuggestedQuestionsUpdate
from app.core.exceptions import NotFoundException, ValidationException, ServiceException
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)


class SuggestedQuestionsService:
    """
    Service for generating and managing suggested questions.
    """
    
    def __init__(self):
        """Initialize suggested questions service."""
        self.llm_service = get_llm_service()
        self.retrieval_service = get_retrieval_service()
    
    def get_suggested_questions(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get suggested questions for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            List of suggested questions
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get suggested questions from widget settings
        widget_settings = bot.widget_settings or {}
        suggested_questions = widget_settings.get("suggested_questions", [])
        
        # Format questions
        formatted_questions = []
        for i, question in enumerate(suggested_questions):
            if isinstance(question, dict):
                formatted_questions.append({
                    "id": question.get("id", str(uuid.uuid4())),
                    "text": question.get("text", ""),
                    "category": question.get("category"),
                    "display_order": question.get("display_order", i)
                })
            else:
                # Handle string questions
                formatted_questions.append({
                    "id": str(uuid.uuid4()),
                    "text": question,
                    "category": None,
                    "display_order": i
                })
        
        return formatted_questions
    
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
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Initialize widget settings if not present
        if not bot.widget_settings:
            bot.widget_settings = {}
        
        # Update suggested questions
        questions = [q.model_dump() for q in questions_data.questions]
        
        # Ensure each question has an ID
        for question in questions:
            if "id" not in question:
                question["id"] = str(uuid.uuid4())
        
        bot.widget_settings["suggested_questions"] = questions
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Suggested questions updated for bot: {bot_id}")
        return bot
    
    async def generate_suggested_questions(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        count: int = 5,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate suggested questions from knowledge base.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            count: Number of questions to generate
            categories: Optional list of categories to focus on
            
        Returns:
            List of generated questions
        """
        try:
            # Get bot
            bot = db.query(Bot).filter(
                Bot.id == bot_id,
                Bot.organization_id == organization_id
            ).first()
            
            if not bot:
                raise NotFoundException(f"Bot with ID {bot_id} not found")
            
            # Get knowledge sources
            knowledge_sources = db.query(KnowledgeSource).filter(
                KnowledgeSource.bot_id == bot_id
            ).all()
            
            if not knowledge_sources:
                logger.warning(f"No knowledge sources found for bot {bot_id}")
                return []
            
            # Get sample chunks from each source
            chunks = []
            for source in knowledge_sources:
                source_chunks = db.query(Chunk).filter(
                    Chunk.source_id == source.id
                ).limit(3).all()
                chunks.extend(source_chunks)
            
            if not chunks:
                logger.warning(f"No chunks found for bot {bot_id}")
                return []
            
            # Prepare context from chunks
            context = "\n\n".join([chunk.content for chunk in chunks])
            
            # Generate questions using LLM
            prompt = f"""
            Based on the following content, generate {count} relevant and specific questions that a user might ask.
            The questions should be diverse and cover different aspects of the content.
            
            Content:
            {context[:4000]}  # Limit context to avoid token limits
            
            Generate {count} questions in the following format:
            1. [Question 1]
            2. [Question 2]
            ...
            
            Make the questions natural, conversational, and specific to the content.
            """
            
            # Call LLM service
            response = self.llm_service.generate_response(
                user_message=prompt,
                bot_settings={
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "model": "gpt-3.5-turbo"
                }
            )
            
            # Parse generated questions
            generated_text = response["content"]
            question_lines = [line.strip() for line in generated_text.split("\n") if line.strip()]
            
            # Extract questions (remove numbering)
            questions = []
            for line in question_lines:
                # Skip non-question lines
                if not any(line.startswith(f"{i}.") for i in range(1, count + 1)):
                    continue
                
                # Remove numbering
                question_text = line.split(".", 1)[-1].strip()
                
                # Create question object
                questions.append({
                    "id": str(uuid.uuid4()),
                    "text": question_text,
                    "category": "generated",
                    "display_order": len(questions)
                })
            
            logger.info(f"Generated {len(questions)} suggested questions for bot {bot_id}")
            return questions
            
        except Exception as e:
            logger.error(f"Failed to generate suggested questions: {str(e)}")
            raise ServiceException(f"Failed to generate suggested questions: {str(e)}")
    
    def add_suggested_question(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        question: SuggestedQuestion
    ) -> Dict[str, Any]:
        """
        Add a single suggested question.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            question: Question to add
            
        Returns:
            Added question with ID
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Initialize widget settings if not present
        if not bot.widget_settings:
            bot.widget_settings = {}
        
        # Initialize suggested questions if not present
        if "suggested_questions" not in bot.widget_settings:
            bot.widget_settings["suggested_questions"] = []
        
        # Create question object
        question_dict = question.dict()
        question_dict["id"] = str(uuid.uuid4())
        
        # Add question
        bot.widget_settings["suggested_questions"].append(question_dict)
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Added suggested question for bot: {bot_id}")
        return question_dict
    
    def delete_suggested_question(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        question_id: str
    ) -> Dict[str, Any]:
        """
        Delete a suggested question.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            question_id: Question ID to delete
            
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
        
        # Check if bot has suggested questions
        if not bot.widget_settings or "suggested_questions" not in bot.widget_settings:
            raise NotFoundException(f"No suggested questions found for bot {bot_id}")
        
        # Find question by ID
        questions = bot.widget_settings["suggested_questions"]
        question_index = None
        for i, q in enumerate(questions):
            if isinstance(q, dict) and q.get("id") == question_id:
                question_index = i
                break
        
        if question_index is None:
            raise NotFoundException(f"Question with ID {question_id} not found")
        
        # Remove question
        removed_question = questions.pop(question_index)
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Deleted suggested question {question_id} for bot: {bot_id}")
        return {
            "success": True,
            "message": f"Question deleted successfully",
            "deleted_question": removed_question
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_suggested_questions_service = None


def get_suggested_questions_service() -> SuggestedQuestionsService:
    """
    Get the global suggested questions service instance.
    
    Returns:
        SuggestedQuestionsService: Global instance
    """
    global _suggested_questions_service
    
    if _suggested_questions_service is None:
        _suggested_questions_service = SuggestedQuestionsService()
    
    return _suggested_questions_service
