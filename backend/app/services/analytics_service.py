"""
Analytics Service

This module provides services for collecting and calculating analytics data.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.organization import Organization
from app.db.models.bot import Bot
from app.db.models.conversation import Conversation, Message
from app.db.models.knowledge_base import KnowledgeSource
from app.db.models.user import User
from app.core.exceptions import NotFoundException


class AnalyticsService:
    """Service for collecting and calculating analytics data"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
    
    async def get_organization_overview(self, organization_id: str) -> Dict[str, Any]:
        """
        Get overview analytics for an organization.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            Dict with organization analytics
            
        Raises:
            NotFoundException: If organization not found
        """
        # Check if organization exists
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await self.db.execute(org_query)
        org = org_result.scalar_one_or_none()
        
        if not org:
            raise NotFoundException(f"Organization with ID {organization_id} not found")
        
        # Get total bots count
        bots_query = select(func.count()).select_from(Bot).where(Bot.organization_id == organization_id)
        bots_result = await self.db.execute(bots_query)
        total_bots = bots_result.scalar_one()
        
        # Get active bots count
        active_bots_query = select(func.count()).select_from(Bot).where(
            and_(Bot.organization_id == organization_id, Bot.status == "active")
        )
        active_bots_result = await self.db.execute(active_bots_query)
        active_bots = active_bots_result.scalar_one()
        
        # Get total conversations count
        conversations_query = select(func.count()).select_from(Conversation).where(
            Conversation.organization_id == organization_id
        )
        conversations_result = await self.db.execute(conversations_query)
        total_conversations = conversations_result.scalar_one()
        
        # Get total messages count
        messages_query = (
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.organization_id == organization_id)
        )
        messages_result = await self.db.execute(messages_query)
        total_messages = messages_result.scalar_one()
        
        # Get total knowledge sources count
        sources_query = (
            select(func.count())
            .select_from(KnowledgeSource)
            .join(Bot, KnowledgeSource.bot_id == Bot.id)
            .where(Bot.organization_id == organization_id)
        )
        sources_result = await self.db.execute(sources_query)
        total_knowledge_sources = sources_result.scalar_one()
        
        # Get member count
        members_query = (
            select(func.count())
            .select_from(User)
            .join(User.memberships)
            .where(User.memberships.any(organization_id=organization_id))
        )
        members_result = await self.db.execute(members_query)
        total_members = members_result.scalar_one()
        
        return {
            "organization_id": organization_id,
            "organization_name": org.name,
            "total_bots": total_bots,
            "active_bots": active_bots,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_knowledge_sources": total_knowledge_sources,
            "total_members": total_members,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_organization_growth(self, organization_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get growth analytics for an organization over a time period.
        
        Args:
            organization_id: Organization ID
            days: Number of days to look back
            
        Returns:
            Dict with growth analytics
        """
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get conversations in the period
        new_conversations_query = (
            select(func.count())
            .select_from(Conversation)
            .where(
                and_(
                    Conversation.organization_id == organization_id,
                    Conversation.created_at >= start_date
                )
            )
        )
        new_conversations_result = await self.db.execute(new_conversations_query)
        new_conversations = new_conversations_result.scalar_one()
        
        # Get messages in the period
        new_messages_query = (
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                and_(
                    Conversation.organization_id == organization_id,
                    Message.created_at >= start_date
                )
            )
        )
        new_messages_result = await self.db.execute(new_messages_query)
        new_messages = new_messages_result.scalar_one()
        
        # Get bots created in the period
        new_bots_query = (
            select(func.count())
            .select_from(Bot)
            .where(
                and_(
                    Bot.organization_id == organization_id,
                    Bot.created_at >= start_date
                )
            )
        )
        new_bots_result = await self.db.execute(new_bots_query)
        new_bots = new_bots_result.scalar_one()
        
        # Get knowledge sources created in the period
        new_sources_query = (
            select(func.count())
            .select_from(KnowledgeSource)
            .join(Bot, KnowledgeSource.bot_id == Bot.id)
            .where(
                and_(
                    Bot.organization_id == organization_id,
                    KnowledgeSource.created_at >= start_date
                )
            )
        )
        new_sources_result = await self.db.execute(new_sources_query)
        new_sources = new_sources_result.scalar_one()
        
        return {
            "organization_id": organization_id,
            "period_days": days,
            "new_conversations": new_conversations,
            "new_messages": new_messages,
            "new_bots": new_bots,
            "new_knowledge_sources": new_sources,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat()
        }
    
    async def get_daily_activity(self, organization_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily activity analytics for an organization.
        
        Args:
            organization_id: Organization ID
            days: Number of days to look back
            
        Returns:
            List of daily activity data
        """
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily message counts
        daily_messages_query = (
            select(
                func.date_trunc('day', Message.created_at).label('day'),
                func.count().label('count')
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                and_(
                    Conversation.organization_id == organization_id,
                    Message.created_at >= start_date
                )
            )
            .group_by(func.date_trunc('day', Message.created_at))
            .order_by(func.date_trunc('day', Message.created_at))
        )
        daily_messages_result = await self.db.execute(daily_messages_query)
        daily_messages = [(day.isoformat(), count) for day, count in daily_messages_result.all()]
        
        # Get daily conversation counts
        daily_conversations_query = (
            select(
                func.date_trunc('day', Conversation.created_at).label('day'),
                func.count().label('count')
            )
            .where(
                and_(
                    Conversation.organization_id == organization_id,
                    Conversation.created_at >= start_date
                )
            )
            .group_by(func.date_trunc('day', Conversation.created_at))
            .order_by(func.date_trunc('day', Conversation.created_at))
        )
        daily_conversations_result = await self.db.execute(daily_conversations_query)
        daily_conversations = [(day.isoformat(), count) for day, count in daily_conversations_result.all()]
        
        # Generate all days in range
        all_days = []
        current_date = start_date
        while current_date <= datetime.utcnow():
            day_str = current_date.date().isoformat()
            all_days.append(day_str)
            current_date += timedelta(days=1)
        
        # Convert to dictionaries with all days
        messages_by_day = {day: 0 for day in all_days}
        conversations_by_day = {day: 0 for day in all_days}
        
        # Fill in actual data
        for day, count in daily_messages:
            day_str = day.split('T')[0]
            if day_str in messages_by_day:
                messages_by_day[day_str] = count
                
        for day, count in daily_conversations:
            day_str = day.split('T')[0]
            if day_str in conversations_by_day:
                conversations_by_day[day_str] = count
        
        # Format response
        daily_stats = []
        for day in all_days:
            daily_stats.append({
                "date": day,
                "messages": messages_by_day[day],
                "conversations": conversations_by_day[day]
            })
        
        return daily_stats
    
    async def get_top_bots(self, organization_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top performing bots for an organization.
        
        Args:
            organization_id: Organization ID
            limit: Maximum number of bots to return
            
        Returns:
            List of top bots with stats
        """
        # Get bots with conversation and message counts
        query = (
            select(
                Bot.id,
                Bot.name,
                Bot.status,
                func.count(Conversation.id).label('conversation_count'),
                func.count(Message.id).label('message_count')
            )
            .outerjoin(Conversation, Conversation.bot_id == Bot.id)
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .where(Bot.organization_id == organization_id)
            .group_by(Bot.id, Bot.name, Bot.status)
            .order_by(desc('message_count'))
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        top_bots = result.all()
        
        # Format response
        return [
            {
                "bot_id": bot_id,
                "name": name,
                "status": status,
                "conversation_count": conversation_count,
                "message_count": message_count
            }
            for bot_id, name, status, conversation_count, message_count in top_bots
        ]
        
    async def get_bot_performance(self, bot_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get detailed performance analytics for a specific bot.
        
        Args:
            bot_id: Bot ID
            days: Number of days to look back
            
        Returns:
            Dict with bot performance analytics
            
        Raises:
            NotFoundException: If bot not found
        """
        # Check if bot exists
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get total conversations
        conversations_query = select(func.count()).select_from(Conversation).where(
            and_(
                Conversation.bot_id == bot_id,
                Conversation.created_at >= start_date
            )
        )
        conversations_result = await self.db.execute(conversations_query)
        total_conversations = conversations_result.scalar_one()
        
        # Get total messages
        messages_query = (
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                and_(
                    Conversation.bot_id == bot_id,
                    Message.created_at >= start_date
                )
            )
        )
        messages_result = await self.db.execute(messages_query)
        total_messages = messages_result.scalar_one()
        
        # Get average messages per conversation
        avg_messages_query = (
            select(func.avg(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == Conversation.id)
                .scalar_subquery()
            ))
            .select_from(Conversation)
            .where(
                and_(
                    Conversation.bot_id == bot_id,
                    Conversation.created_at >= start_date
                )
            )
        )
        avg_messages_result = await self.db.execute(avg_messages_query)
        avg_messages_per_conversation = avg_messages_result.scalar_one() or 0
        
        # Get average response time (if available in your schema)
        avg_response_time = 0  # Placeholder, implement based on your schema
        
        # Get daily conversation counts
        daily_conversations_query = (
            select(
                func.date_trunc('day', Conversation.created_at).label('day'),
                func.count().label('count')
            )
            .where(
                and_(
                    Conversation.bot_id == bot_id,
                    Conversation.created_at >= start_date
                )
            )
            .group_by(func.date_trunc('day', Conversation.created_at))
            .order_by(func.date_trunc('day', Conversation.created_at))
        )
        daily_conversations_result = await self.db.execute(daily_conversations_query)
        daily_conversations = [(day.isoformat(), count) for day, count in daily_conversations_result.all()]
        
        # Generate all days in range
        all_days = []
        current_date = start_date
        while current_date <= datetime.utcnow():
            day_str = current_date.date().isoformat()
            all_days.append(day_str)
            current_date += timedelta(days=1)
        
        # Convert to dictionary with all days
        conversations_by_day = {day: 0 for day in all_days}
        
        # Fill in actual data
        for day, count in daily_conversations:
            day_str = day.split('T')[0]
            if day_str in conversations_by_day:
                conversations_by_day[day_str] = count
        
        # Format daily data
        daily_stats = []
        for day in all_days:
            daily_stats.append({
                "date": day,
                "conversations": conversations_by_day[day]
            })
        
        # Get knowledge source usage
        sources_query = (
            select(
                KnowledgeSource.id,
                KnowledgeSource.name,
                KnowledgeSource.source_type,
                func.count(Message.id).label('usage_count')
            )
            .join(Bot, KnowledgeSource.bot_id == Bot.id)
            .join(Conversation, Conversation.bot_id == Bot.id)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                and_(
                    Bot.id == bot_id,
                    Message.created_at >= start_date
                )
            )
            .group_by(KnowledgeSource.id, KnowledgeSource.name, KnowledgeSource.source_type)
            .order_by(desc('usage_count'))
        )
        sources_result = await self.db.execute(sources_query)
        sources = [
            {
                "source_id": source_id,
                "name": name,
                "source_type": source_type,
                "usage_count": usage_count
            }
            for source_id, name, source_type, usage_count in sources_result.all()
        ]
        
        return {
            "bot_id": bot_id,
            "bot_name": bot.name,
            "period_days": days,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "avg_messages_per_conversation": round(avg_messages_per_conversation, 2),
            "avg_response_time_ms": avg_response_time,
            "daily_stats": daily_stats,
            "knowledge_sources": sources
        }
        
    async def get_bot_conversation_details(self, bot_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent conversation details for a bot.
        
        Args:
            bot_id: Bot ID
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation details
        """
        # Check if bot exists
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get recent conversations
        conversations_query = (
            select(Conversation)
            .where(Conversation.bot_id == bot_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        conversations_result = await self.db.execute(conversations_query)
        conversations = conversations_result.scalars().all()
        
        # Get message counts for each conversation
        conversation_details = []
        for conversation in conversations:
            # Get message count
            message_count_query = (
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation.id)
            )
            message_count_result = await self.db.execute(message_count_query)
            message_count = message_count_result.scalar_one()
            
            # Format conversation details
            conversation_details.append({
                "conversation_id": conversation.id,
                "started_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
                "duration": (conversation.ended_at - conversation.created_at).total_seconds() if conversation.ended_at else None,
                "message_count": message_count,
                "visitor_id": conversation.visitor_id,
                "rating": conversation.rating,
                "feedback": conversation.feedback
            })
        
        return conversation_details


# Factory function to get analytics service instance
def get_analytics_service() -> AnalyticsService:
    """
    Factory function to get an AnalyticsService instance.
    
    Returns:
        AnalyticsService: New instance of analytics service
    """
    return AnalyticsService()