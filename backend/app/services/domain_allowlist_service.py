import logging
from typing import List, Dict, Any, Optional, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.db.models.bot import Bot
from app.core.exceptions import NotFoundException, ForbiddenException, ValidationError

logger = logging.getLogger(__name__)

class DomainAllowlistService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_allowed_domains(self, bot_id: str, organization_id: str) -> List[str]:
        """
        Get the list of allowed domains for a bot.
        
        Args:
            bot_id: The ID of the bot
            organization_id: The ID of the organization (for validation)
            
        Returns:
            List[str]: List of allowed domains
            
        Raises:
            NotFoundException: If bot not found
            ForbiddenException: If bot doesn't belong to organization
        """
        bot = await self._get_bot_with_validation(bot_id, organization_id)
        return bot.allowed_domains or []
    
    async def add_domain(self, bot_id: str, organization_id: str, domain: str) -> List[str]:
        """
        Add a domain to the bot's allowed domains list.
        
        Args:
            bot_id: The ID of the bot
            organization_id: The ID of the organization (for validation)
            domain: The domain to add
            
        Returns:
            List[str]: Updated list of allowed domains
            
        Raises:
            NotFoundException: If bot not found
            ForbiddenException: If bot doesn't belong to organization
            ValidationError: If domain format is invalid
        """
        # Validate domain format
        self._validate_domain(domain)
        
        bot = await self._get_bot_with_validation(bot_id, organization_id)
        
        # Initialize allowed_domains if None
        if bot.allowed_domains is None:
            bot.allowed_domains = []
        
        # Check if domain already exists
        if domain in bot.allowed_domains:
            return bot.allowed_domains
        
        # Add domain to list
        bot.allowed_domains.append(domain)
        self.db.add(bot)
        await self.db.commit()
        await self.db.refresh(bot)
        
        return bot.allowed_domains
    
    async def remove_domain(self, bot_id: str, organization_id: str, domain: str) -> List[str]:
        """
        Remove a domain from the bot's allowed domains list.
        
        Args:
            bot_id: The ID of the bot
            organization_id: The ID of the organization (for validation)
            domain: The domain to remove
            
        Returns:
            List[str]: Updated list of allowed domains
            
        Raises:
            NotFoundException: If bot not found or domain not in list
            ForbiddenException: If bot doesn't belong to organization
        """
        bot = await self._get_bot_with_validation(bot_id, organization_id)
        
        # Check if allowed_domains exists and domain is in list
        if not bot.allowed_domains or domain not in bot.allowed_domains:
            raise NotFoundException(f"Domain {domain} not found in bot's allowed domains")
        
        # Remove domain from list
        bot.allowed_domains.remove(domain)
        self.db.add(bot)
        await self.db.commit()
        await self.db.refresh(bot)
        
        return bot.allowed_domains
    
    async def update_domains(self, bot_id: str, organization_id: str, domains: List[str]) -> List[str]:
        """
        Replace the entire allowed domains list for a bot.
        
        Args:
            bot_id: The ID of the bot
            organization_id: The ID of the organization (for validation)
            domains: The new list of allowed domains
            
        Returns:
            List[str]: Updated list of allowed domains
            
        Raises:
            NotFoundException: If bot not found
            ForbiddenException: If bot doesn't belong to organization
            ValidationError: If any domain format is invalid
        """
        # Validate all domains
        for domain in domains:
            self._validate_domain(domain)
        
        bot = await self._get_bot_with_validation(bot_id, organization_id)
        
        # Replace domains list
        bot.allowed_domains = domains
        self.db.add(bot)
        await self.db.commit()
        await self.db.refresh(bot)
        
        return bot.allowed_domains
    
    async def is_domain_allowed(self, bot_id: str, domain: str) -> bool:
        """
        Check if a domain is allowed for a bot.
        
        Args:
            bot_id: The ID of the bot
            domain: The domain to check
            
        Returns:
            bool: True if domain is allowed, False otherwise
        """
        bot = await self.db.get(Bot, bot_id)
        if not bot:
            return False
        
        # If no allowed domains are set, allow all domains
        if not bot.allowed_domains or len(bot.allowed_domains) == 0:
            return True
        
        # Check if domain matches any allowed domain (including wildcards)
        return self._is_domain_in_allowlist(domain, bot.allowed_domains)
    
    async def _get_bot_with_validation(self, bot_id: str, organization_id: str) -> Bot:
        """
        Get a bot and validate that it belongs to the organization.
        
        Args:
            bot_id: The ID of the bot
            organization_id: The ID of the organization
            
        Returns:
            Bot: The bot object
            
        Raises:
            NotFoundException: If bot not found
            ForbiddenException: If bot doesn't belong to organization
        """
        bot = await self.db.execute(
            select(Bot).where(Bot.id == bot_id)
        )
        bot = bot.scalar_one_or_none()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        if bot.organization_id != organization_id:
            raise ForbiddenException(f"Bot with ID {bot_id} does not belong to organization {organization_id}")
        
        return bot
    
    def _validate_domain(self, domain: str) -> None:
        """
        Validate domain format.
        
        Args:
            domain: The domain to validate
            
        Raises:
            ValidationError: If domain format is invalid
        """
        # Allow wildcards at the beginning of domain segments
        if domain == "*":
            return
        
        # Basic domain validation regex
        # Allows wildcard subdomains like *.example.com
        domain_regex = r'^(\*\.)?([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        
        if not re.match(domain_regex, domain):
            raise ValidationError(f"Invalid domain format: {domain}")
    
    def _is_domain_in_allowlist(self, domain: str, allowed_domains: List[str]) -> bool:
        """
        Check if a domain matches any domain in the allowlist, including wildcards.
        
        Args:
            domain: The domain to check
            allowed_domains: List of allowed domains
            
        Returns:
            bool: True if domain is allowed, False otherwise
        """
        # Exact match
        if domain in allowed_domains:
            return True
        
        # Wildcard match
        domain_parts = domain.split('.')
        for allowed_domain in allowed_domains:
            # Check for global wildcard
            if allowed_domain == "*":
                return True
            
            # Check for wildcard subdomain
            if allowed_domain.startswith('*.'):
                wildcard_suffix = allowed_domain[1:]  # Remove the *
                if domain.endswith(wildcard_suffix):
                    return True
        
        return False
