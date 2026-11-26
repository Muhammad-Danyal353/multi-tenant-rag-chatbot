"""
API Key Service

This module provides services for managing API keys.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from app.db.session import get_db, get_async_db
from app.db.models.bot import Bot
from app.core.security import generate_api_key, hash_api_key
from app.core.exceptions import NotFoundException
from app.services.audit_service import AuditService


class ApiKeyService:
    """Service for managing API keys"""
    
    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
        self.audit_service = AuditService(db)
    
    async def generate_api_key_for_bot(
        self, 
        bot_id: str,
        user_id: str,
        name: str,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a new API key for a bot.
        
        Args:
            bot_id: Bot ID
            user_id: User ID creating the key
            name: Name/description for the API key
            expires_in_days: Optional expiration in days
            
        Returns:
            Dict with API key details
            
        Raises:
            NotFoundException: If bot not found
        """
        # Check if bot exists
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Generate API key
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)
        
        # Calculate expiration date if provided
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        from app.db.models.api_key import ApiKey
        
        api_key_record = ApiKey(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            name=name,
            key_hash=api_key_hash,
            created_by=user_id,
            expires_at=expires_at,
            is_active=True
        )
        
        self.db.add(api_key_record)
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            organization_id=bot.organization_id,
            user_id=user_id,
            action="create",
            resource_type="api_key",
            resource_id=api_key_record.id,
            changes={"bot_id": bot_id, "name": name}
        )
        
        # Return API key details
        return {
            "id": api_key_record.id,
            "bot_id": bot_id,
            "name": name,
            "api_key": api_key,  # Only returned once
            "created_at": api_key_record.created_at,
            "expires_at": expires_at,
            "is_active": api_key_record.is_active
        }
    
    async def list_api_keys(self, bot_id: str) -> List[Dict[str, Any]]:
        """
        List all API keys for a bot.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            List of API key details (without the actual keys)
            
        Raises:
            NotFoundException: If bot not found
        """
        # Check if bot exists
        bot_query = select(Bot).where(Bot.id == bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get API keys
        from app.db.models.api_key import ApiKey
        
        keys_query = (
            select(ApiKey)
            .where(ApiKey.bot_id == bot_id)
            .order_by(ApiKey.created_at.desc())
        )
        
        keys_result = await self.db.execute(keys_query)
        keys = keys_result.scalars().all()
        
        # Format response
        return [
            {
                "id": key.id,
                "bot_id": key.bot_id,
                "name": key.name,
                "created_at": key.created_at,
                "created_by": key.created_by,
                "expires_at": key.expires_at,
                "is_active": key.is_active,
                "last_used_at": key.last_used_at
            }
            for key in keys
        ]
    
    async def revoke_api_key(
        self, 
        key_id: str,
        user_id: str
    ) -> bool:
        """
        Revoke (deactivate) an API key.
        
        Args:
            key_id: API key ID
            user_id: User ID performing the revocation
            
        Returns:
            True if successful
            
        Raises:
            NotFoundException: If API key not found
        """
        # Get API key
        from app.db.models.api_key import ApiKey
        
        key_query = select(ApiKey).where(ApiKey.id == key_id)
        key_result = await self.db.execute(key_query)
        key = key_result.scalar_one_or_none()
        
        if not key:
            raise NotFoundException(f"API key with ID {key_id} not found")
        
        # Get bot for organization ID
        bot_query = select(Bot).where(Bot.id == key.bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {key.bot_id} not found")
        
        # Deactivate the key
        key.is_active = False
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            organization_id=bot.organization_id,
            user_id=user_id,
            action="revoke",
            resource_type="api_key",
            resource_id=key_id
        )
        
        return True
    
    async def rotate_api_key(
        self, 
        key_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Rotate (replace) an API key.
        
        Args:
            key_id: API key ID
            user_id: User ID performing the rotation
            
        Returns:
            Dict with new API key details
            
        Raises:
            NotFoundException: If API key not found
        """
        # Get API key
        from app.db.models.api_key import ApiKey
        
        key_query = select(ApiKey).where(ApiKey.id == key_id)
        key_result = await self.db.execute(key_query)
        key = key_result.scalar_one_or_none()
        
        if not key:
            raise NotFoundException(f"API key with ID {key_id} not found")
        
        # Get bot for organization ID
        bot_query = select(Bot).where(Bot.id == key.bot_id)
        bot_result = await self.db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {key.bot_id} not found")
        
        # Generate new API key
        new_api_key = generate_api_key()
        new_api_key_hash = hash_api_key(new_api_key)
        
        # Update the key
        key.key_hash = new_api_key_hash
        key.created_at = datetime.utcnow()
        key.created_by = user_id
        key.is_active = True
        
        await self.db.commit()
        
        # Log the action
        await self.audit_service.log_action(
            organization_id=bot.organization_id,
            user_id=user_id,
            action="rotate",
            resource_type="api_key",
            resource_id=key_id
        )
        
        # Return API key details
        return {
            "id": key.id,
            "bot_id": key.bot_id,
            "name": key.name,
            "api_key": new_api_key,  # Only returned once
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "is_active": key.is_active
        }
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return the associated bot.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Optional[Dict]: Bot details if key is valid, None otherwise
        """
        # Hash the API key
        api_key_hash = hash_api_key(api_key)
        
        # Find the API key
        from app.db.models.api_key import ApiKey
        
        key_query = (
            select(ApiKey, Bot)
            .join(Bot, ApiKey.bot_id == Bot.id)
            .where(
                and_(
                    ApiKey.key_hash == api_key_hash,
                    ApiKey.is_active == True,
                    or_(
                        ApiKey.expires_at.is_(None),
                        ApiKey.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        
        key_result = await self.db.execute(key_query)
        key_with_bot = key_result.one_or_none()
        
        if not key_with_bot:
            return None
            
        key, bot = key_with_bot
        
        # Update last used timestamp
        key.last_used_at = datetime.utcnow()
        await self.db.commit()
        
        # Return bot details
        return {
            "bot_id": bot.id,
            "bot_name": bot.name,
            "organization_id": bot.organization_id,
            "api_key_id": key.id,
            "api_key_name": key.name
        }


# Alias for backward compatibility
APIKeyService = ApiKeyService
