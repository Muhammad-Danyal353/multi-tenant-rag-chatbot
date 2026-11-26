"""
Stats Service

This module provides services for collecting and calculating platform statistics.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db, get_async_db
from app.db.models.user import User
from app.db.models.organization import Organization, SubscriptionStatus, SubscriptionPlan
from app.db.models.bot import Bot
from app.db.models.conversation import Conversation, Message
from app.db.models.knowledge_base import KnowledgeSource


class StatsService:
    """Service for collecting and calculating platform statistics"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
    
    async def get_platform_overview(self) -> Dict[str, Any]:
        """
        Get platform-wide overview statistics.
        
        Returns:
            Dict with platform statistics
        """
        # Get total users count
        users_query = select(func.count()).select_from(User)
        users_result = await self.db.execute(users_query)
        total_users = users_result.scalar_one()
        
        # Get active organizations count
        active_orgs_query = select(func.count()).select_from(Organization).where(Organization.is_active == True)
        active_orgs_result = await self.db.execute(active_orgs_query)
        active_organizations = active_orgs_result.scalar_one()
        
        # Get total organizations count
        orgs_query = select(func.count()).select_from(Organization)
        orgs_result = await self.db.execute(orgs_query)
        total_organizations = orgs_result.scalar_one()
        
        # Get total bots count
        bots_query = select(func.count()).select_from(Bot)
        bots_result = await self.db.execute(bots_query)
        total_bots = bots_result.scalar_one()
        
        # Get total conversations count
        conversations_query = select(func.count()).select_from(Conversation)
        conversations_result = await self.db.execute(conversations_query)
        total_conversations = conversations_result.scalar_one()
        
        # Get total messages count
        messages_query = select(func.count()).select_from(Message)
        messages_result = await self.db.execute(messages_query)
        total_messages = messages_result.scalar_one()
        
        # Get total knowledge sources count
        sources_query = select(func.count()).select_from(KnowledgeSource)
        sources_result = await self.db.execute(sources_query)
        total_knowledge_sources = sources_result.scalar_one()
        
        return {
            "total_users": total_users,
            "total_organizations": total_organizations,
            "active_organizations": active_organizations,
            "total_bots": total_bots,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_knowledge_sources": total_knowledge_sources,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_growth_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get growth statistics for the specified number of days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict with growth statistics
        """
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get users registered in the period
        new_users_query = select(func.count()).select_from(User).where(User.created_at >= start_date)
        new_users_result = await self.db.execute(new_users_query)
        new_users = new_users_result.scalar_one()
        
        # Get organizations created in the period
        new_orgs_query = select(func.count()).select_from(Organization).where(Organization.created_at >= start_date)
        new_orgs_result = await self.db.execute(new_orgs_query)
        new_organizations = new_orgs_result.scalar_one()
        
        # Get bots created in the period
        new_bots_query = select(func.count()).select_from(Bot).where(Bot.created_at >= start_date)
        new_bots_result = await self.db.execute(new_bots_query)
        new_bots = new_bots_result.scalar_one()
        
        # Get conversations in the period
        new_conversations_query = select(func.count()).select_from(Conversation).where(Conversation.created_at >= start_date)
        new_conversations_result = await self.db.execute(new_conversations_query)
        new_conversations = new_conversations_result.scalar_one()
        
        # Get messages in the period
        new_messages_query = select(func.count()).select_from(Message).where(Message.created_at >= start_date)
        new_messages_result = await self.db.execute(new_messages_query)
        new_messages = new_messages_result.scalar_one()
        
        return {
            "period_days": days,
            "new_users": new_users,
            "new_organizations": new_organizations,
            "new_bots": new_bots,
            "new_conversations": new_conversations,
            "new_messages": new_messages,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat()
        }
    
    async def get_subscription_stats(self) -> Dict[str, Any]:
        """
        Get statistics about subscription plans and statuses.
        
        Returns:
            Dict with subscription statistics
        """
        # Get organizations by plan
        plans_query = (
            select(Organization.subscription_plan, func.count())
            .group_by(Organization.subscription_plan)
        )
        plans_result = await self.db.execute(plans_query)
        plans_data = {plan.value: count for plan, count in plans_result.all()}
        
        # Get organizations by status
        statuses_query = (
            select(Organization.subscription_status, func.count())
            .group_by(Organization.subscription_status)
        )
        statuses_result = await self.db.execute(statuses_query)
        statuses_data = {status.value: count for status, count in statuses_result.all()}
        
        # Calculate percentages
        total_orgs = sum(plans_data.values())
        plan_percentages = {
            plan: round((count / total_orgs) * 100, 2) if total_orgs > 0 else 0
            for plan, count in plans_data.items()
        }
        
        return {
            "plans": plans_data,
            "statuses": statuses_data,
            "plan_percentages": plan_percentages,
            "total_organizations": total_orgs
        }
    
    async def get_daily_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily activity statistics for the specified number of days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily activity statistics
        """
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily message counts
        daily_messages_query = (
            select(
                func.date_trunc('day', Message.created_at).label('day'),
                func.count().label('count')
            )
            .where(Message.created_at >= start_date)
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
            .where(Conversation.created_at >= start_date)
            .group_by(func.date_trunc('day', Conversation.created_at))
            .order_by(func.date_trunc('day', Conversation.created_at))
        )
        daily_conversations_result = await self.db.execute(daily_conversations_query)
        daily_conversations = [(day.isoformat(), count) for day, count in daily_conversations_result.all()]
        
        # Get daily user registrations
        daily_users_query = (
            select(
                func.date_trunc('day', User.created_at).label('day'),
                func.count().label('count')
            )
            .where(User.created_at >= start_date)
            .group_by(func.date_trunc('day', User.created_at))
            .order_by(func.date_trunc('day', User.created_at))
        )
        daily_users_result = await self.db.execute(daily_users_query)
        daily_users = [(day.isoformat(), count) for day, count in daily_users_result.all()]
        
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
        users_by_day = {day: 0 for day in all_days}
        
        # Fill in actual data
        for day, count in daily_messages:
            day_str = day.split('T')[0]
            if day_str in messages_by_day:
                messages_by_day[day_str] = count
                
        for day, count in daily_conversations:
            day_str = day.split('T')[0]
            if day_str in conversations_by_day:
                conversations_by_day[day_str] = count
                
        for day, count in daily_users:
            day_str = day.split('T')[0]
            if day_str in users_by_day:
                users_by_day[day_str] = count
        
        # Format response
        daily_stats = []
        for day in all_days:
            daily_stats.append({
                "date": day,
                "messages": messages_by_day[day],
                "conversations": conversations_by_day[day],
                "new_users": users_by_day[day]
            })
        
        return daily_stats
    
    async def get_top_organizations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top organizations by message count.
        
        Args:
            limit: Maximum number of organizations to return
            
        Returns:
            List of top organizations
        """
        # Get organizations with message counts
        query = (
            select(
                Organization.id,
                Organization.name,
                Organization.subscription_plan,
                func.count(Message.id).label('message_count')
            )
            .join(Conversation, Conversation.organization_id == Organization.id)
            .join(Message, Message.conversation_id == Conversation.id)
            .group_by(Organization.id, Organization.name, Organization.subscription_plan)
            .order_by(desc('message_count'))
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        top_orgs = result.all()
        
        # Format response
        return [
            {
                "id": org_id,
                "name": name,
                "subscription_plan": plan.value,
                "message_count": count
            }
            for org_id, name, plan, count in top_orgs
        ]
