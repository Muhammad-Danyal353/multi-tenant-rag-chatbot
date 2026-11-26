"""
Chat Service

Handles chat conversations and message processing:
- Message storage and retrieval
- Context management
- LLM integration
- Source attribution
- Conversation analytics
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation, Message
from app.db.models.bot import Bot
from app.services.retrieval_service import get_retrieval_service
from app.services.llm_service import get_llm_service
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    ChatException
)
from app.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing chat conversations and message processing.
    """
    
    def __init__(self):
        """Initialize chat service."""
        self.retrieval_service = get_retrieval_service()
        self.llm_service = get_llm_service()
        
        # Context management settings
        self.max_context_messages = 10
        self.max_context_tokens = 4000
    
    def send_message(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        visitor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process and respond to a user message.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID
            message: User message
            conversation_id: Existing conversation ID (optional)
            visitor_id: Visitor ID for anonymous users
            metadata: Additional metadata
            
        Returns:
            Response with AI message and sources
        """
        try:
            start_time = datetime.utcnow()
            
            # 1. Get or create conversation
            conversation = self._get_or_create_conversation(
                db=db,
                bot_id=bot_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                visitor_id=visitor_id,
                metadata=metadata
            )
            
            # 2. Store user message
            user_message = self._store_message(
                db=db,
                conversation_id=conversation.id,
                role="user",
                content=message,
                metadata=metadata
            )
            
            # 3. Retrieve relevant context
            retrieval_results = self.retrieval_service.hybrid_search(
                query=message,
                bot_id=bot_id,
                organization_id=organization_id,
                top_k=settings.DEFAULT_TOP_K
            )
            
            # 4. Get conversation context
            context_messages = self._get_conversation_context(
                db=db,
                conversation_id=conversation.id,
                max_messages=self.max_context_messages
            )
            
            # 5. Generate AI response
            ai_response = self._generate_response(
                user_message=message,
                context_messages=context_messages,
                retrieval_results=retrieval_results,
                bot_id=bot_id,
                db=db
            )
            
            # 6. Store AI message
            ai_message = self._store_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=ai_response["content"],
                sources_used=[r["id"] for r in retrieval_results],
                metadata={
                    "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                    "token_count": ai_response.get("token_count", 0),
                    "model_used": ai_response.get("model_used", settings.DEFAULT_LLM_MODEL)
                }
            )
            
            # 7. Update conversation
            self._update_conversation(
                db=db,
                conversation_id=conversation.id,
                last_message_at=datetime.utcnow()
            )
            
            # 8. Format response
            response = {
                "response": ai_response["content"],
                "conversation_id": str(conversation.id),
                "message_id": str(ai_message.id),
                "sources": self.retrieval_service.get_source_attribution(retrieval_results),
                "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "metadata": {
                    "bot_id": bot_id,
                    "organization_id": organization_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            logger.info(
                f"Message processed successfully: conversation {conversation.id}, "
                f"latency: {response['latency_ms']:.2f}ms"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to process message: {str(e)}")
            raise ChatException(f"Failed to process message: {str(e)}")
    
    def _get_or_create_conversation(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        conversation_id: Optional[str] = None,
        visitor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """
        Get existing conversation or create a new one.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID
            conversation_id: Existing conversation ID
            visitor_id: Visitor ID
            metadata: Additional metadata
            
        Returns:
            Conversation object
        """
        if conversation_id:
            # Get existing conversation
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id,
                Conversation.bot_id == bot_id,
                Conversation.organization_id == organization_id
            ).first()
            
            if not conversation:
                raise NotFoundException("Conversation not found")
            
            return conversation
        else:
            # Create new conversation
            conversation = Conversation(
                id=uuid.uuid4(),
                bot_id=bot_id,
                organization_id=organization_id,
                session_id=str(uuid.uuid4()),
                visitor_id=visitor_id or str(uuid.uuid4()),
                started_at=datetime.utcnow(),
                metadata=metadata or {}
            )
            
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            logger.info(f"Created new conversation: {conversation.id}")
            return conversation
    
    def _store_message(
        self,
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        sources_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Store a message in the database.
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            role: Message role (user/assistant)
            content: Message content
            sources_used: List of source IDs used
            metadata: Additional metadata
            
        Returns:
            Message object
        """
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources_used=sources_used or [],
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return message
    
    def _get_conversation_context(
        self,
        db: Session,
        conversation_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation context for LLM.
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            max_messages: Maximum number of messages to include
            
        Returns:
            List of context messages
        """
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.desc()).limit(max_messages).all()
        
        # Reverse to get chronological order
        messages.reverse()
        
        context = []
        for message in messages:
            context.append({
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat()
            })
        
        return context
    
    def _generate_response(
        self,
        user_message: str,
        context_messages: List[Dict[str, Any]],
        retrieval_results: List[Dict[str, Any]],
        bot_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generate AI response using LLM service.
        
        Args:
            user_message: Current user message
            context_messages: Conversation context
            retrieval_results: Retrieved knowledge chunks
            bot_id: Bot ID
            db: Database session
            
        Returns:
            AI response with metadata
        """
        # Get bot configuration
        bot = db.query(Bot).filter(Bot.id == bot_id).first()
        if not bot:
            raise NotFoundException("Bot not found")
        
        # Prepare context from retrieved knowledge
        knowledge_context = self._format_knowledge_context(retrieval_results)
        
        # Generate response using LLM service
        response = self.llm_service.generate_response(
            user_message=user_message,
            context_messages=context_messages,
            knowledge_context=knowledge_context,
            bot_settings=bot.settings or {},
            system_prompt=bot.system_prompt
        )
        
        return response
    
    def _format_knowledge_context(
        self,
        retrieval_results: List[Dict[str, Any]]
    ) -> str:
        """
        Format retrieved knowledge into context for LLM.
        
        Args:
            retrieval_results: Retrieved knowledge chunks
            
        Returns:
            Formatted knowledge context
        """
        if not retrieval_results:
            return "No relevant knowledge found."
        
        context_parts = []
        for i, result in enumerate(retrieval_results, 1):
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            
            # Format source information
            source_info = f"[Source {i}]"
            if source_type == "document":
                doc_name = metadata.get("document_name", "Unknown Document")
                page = metadata.get("page_number")
                source_info += f" Document: {doc_name}"
                if page:
                    source_info += f" (Page {page})"
            elif source_type == "web":
                title = metadata.get("webpage_title", "Unknown Webpage")
                url = metadata.get("url", "")
                source_info += f" Webpage: {title}"
                if url:
                    source_info += f" ({url})"
            elif source_type == "text":
                title = metadata.get("text_title", "Unknown Text")
                source_info += f" Text: {title}"
            
            context_parts.append(f"{source_info}\n{content}")
        
        return "\n\n".join(context_parts)
    
    def _update_conversation(
        self,
        db: Session,
        conversation_id: str,
        last_message_at: datetime
    ) -> None:
        """
        Update conversation metadata.
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            last_message_at: Timestamp of last message
        """
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if conversation:
            conversation.last_message_at = last_message_at
            db.commit()
    
    def get_conversation(
        self,
        db: Session,
        conversation_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get conversation details and messages.
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            organization_id: Organization ID
            
        Returns:
            Conversation details with messages
        """
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id
        ).first()
        
        if not conversation:
            raise NotFoundException("Conversation not found")
        
        # Get messages
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        return {
            "id": str(conversation.id),
            "bot_id": conversation.bot_id,
            "session_id": conversation.session_id,
            "visitor_id": conversation.visitor_id,
            "started_at": conversation.started_at.isoformat(),
            "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            "rating": conversation.rating,
            "feedback": conversation.feedback,
            "metadata": conversation.metadata,
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "sources_used": msg.sources_used,
                    "metadata": msg.metadata
                }
                for msg in messages
            ]
        }
    
    def list_conversations(
        self,
        db: Session,
        organization_id: str,
        bot_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List conversations for an organization.
        
        Args:
            db: Database session
            organization_id: Organization ID
            bot_id: Optional bot filter
            limit: Number of results
            offset: Offset for pagination
            
        Returns:
            List of conversations with pagination info
        """
        query = db.query(Conversation).filter(
            Conversation.organization_id == organization_id
        )
        
        if bot_id:
            query = query.filter(Conversation.bot_id == bot_id)
        
        # Get total count
        total = query.count()
        
        # Get conversations
        conversations = query.order_by(
            Conversation.last_message_at.desc()
        ).offset(offset).limit(limit).all()
        
        return {
            "conversations": [
                {
                    "id": str(conv.id),
                    "bot_id": conv.bot_id,
                    "session_id": conv.session_id,
                    "visitor_id": conv.visitor_id,
                    "started_at": conv.started_at.isoformat(),
                    "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                    "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                    "rating": conv.rating,
                    "feedback": conv.feedback,
                    "message_count": len(conv.messages) if hasattr(conv, 'messages') else 0
                }
                for conv in conversations
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def submit_feedback(
        self,
        db: Session,
        conversation_id: str,
        organization_id: str,
        rating: int,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit feedback for a conversation.
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            organization_id: Organization ID
            rating: Rating (1-5)
            feedback: Optional text feedback
            
        Returns:
            Success response
        """
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id
        ).first()
        
        if not conversation:
            raise NotFoundException("Conversation not found")
        
        if not (1 <= rating <= 5):
            raise ValidationException("Rating must be between 1 and 5")
        
        conversation.rating = rating
        conversation.feedback = feedback
        db.commit()
        
        logger.info(f"Feedback submitted for conversation {conversation_id}: rating={rating}")
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "conversation_id": conversation_id,
            "rating": rating
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Get the global chat service instance.
    
    Returns:
        ChatService: Global instance
    """
    global _chat_service
    
    if _chat_service is None:
        _chat_service = ChatService()
    
    return _chat_service
