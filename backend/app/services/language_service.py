"""
Language Service

Handles multi-language support for bots:
- Language detection
- Translation
- Language-specific configurations
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.db.models.bot import Bot
from app.core.exceptions import NotFoundException, ValidationException, ServiceException

logger = logging.getLogger(__name__)


class LanguageService:
    """
    Service for multi-language support.
    """
    
    def __init__(self):
        """Initialize language service."""
        # Supported languages with their codes and names
        self.supported_languages = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "nl": "Dutch",
            "ru": "Russian",
            "zh": "Chinese (Simplified)",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic"
        }
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get list of supported languages.
        
        Returns:
            List of language objects with code and name
        """
        return [
            {"code": code, "name": name}
            for code, name in self.supported_languages.items()
        ]
    
    def get_bot_languages(
        self,
        db: Session,
        bot_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get language settings for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            
        Returns:
            Bot language settings
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get language settings
        settings = bot.settings or {}
        language_settings = settings.get("languages", {})
        
        # If no language settings, create default
        if not language_settings:
            language_settings = {
                "default": "en",
                "enabled": ["en"],
                "auto_detect": True,
                "translations": {}
            }
        
        return {
            "settings": language_settings,
            "supported_languages": self.get_supported_languages()
        }
    
    def update_bot_languages(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        language_settings: Dict[str, Any]
    ) -> Bot:
        """
        Update language settings for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            language_settings: Language settings to update
            
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
        
        # Validate language settings
        self._validate_language_settings(language_settings)
        
        # Update language settings
        bot.settings["languages"] = language_settings
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Language settings updated for bot: {bot_id}")
        return bot
    
    def add_language_translation(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        language_code: str,
        translations: Dict[str, str]
    ) -> Bot:
        """
        Add translations for a specific language.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            language_code: Language code
            translations: Dictionary of key-value translations
            
        Returns:
            Updated Bot
        """
        # Validate language code
        if language_code not in self.supported_languages:
            raise ValidationException(f"Language code {language_code} is not supported")
        
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
        
        # Initialize language settings if not present
        if "languages" not in bot.settings:
            bot.settings["languages"] = {
                "default": "en",
                "enabled": ["en"],
                "auto_detect": True,
                "translations": {}
            }
        
        # Initialize translations if not present
        if "translations" not in bot.settings["languages"]:
            bot.settings["languages"]["translations"] = {}
        
        # Add language to enabled languages if not already present
        if language_code not in bot.settings["languages"]["enabled"]:
            bot.settings["languages"]["enabled"].append(language_code)
        
        # Add translations
        if language_code not in bot.settings["languages"]["translations"]:
            bot.settings["languages"]["translations"][language_code] = {}
        
        # Update translations
        bot.settings["languages"]["translations"][language_code].update(translations)
        
        # Save changes
        bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(bot)
        
        logger.info(f"Added translations for language {language_code} to bot: {bot_id}")
        return bot
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of text.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Detected language code
        """
        # This would use a language detection library like langdetect
        # For now, return English as default
        return "en"
    
    def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> str:
        """
        Translate text from source to target language.
        
        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            Translated text
        """
        # This would use a translation API like Google Translate
        # For now, return original text
        return text
    
    def get_language_specific_settings(
        self,
        db: Session,
        bot_id: str,
        organization_id: str,
        language_code: str
    ) -> Dict[str, Any]:
        """
        Get language-specific settings for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            organization_id: Organization ID for validation
            language_code: Language code
            
        Returns:
            Language-specific settings
        """
        # Get bot
        bot = db.query(Bot).filter(
            Bot.id == bot_id,
            Bot.organization_id == organization_id
        ).first()
        
        if not bot:
            raise NotFoundException(f"Bot with ID {bot_id} not found")
        
        # Get language settings
        settings = bot.settings or {}
        language_settings = settings.get("languages", {})
        
        # Get language-specific settings
        language_specific = language_settings.get("language_specific", {}).get(language_code, {})
        
        # Get translations
        translations = language_settings.get("translations", {}).get(language_code, {})
        
        return {
            "language_code": language_code,
            "language_name": self.supported_languages.get(language_code, "Unknown"),
            "settings": language_specific,
            "translations": translations,
            "is_enabled": language_code in language_settings.get("enabled", ["en"]),
            "is_default": language_code == language_settings.get("default", "en")
        }
    
    def _validate_language_settings(self, settings: Dict[str, Any]) -> None:
        """
        Validate language settings.
        
        Args:
            settings: Language settings to validate
            
        Raises:
            ValidationException: If settings are invalid
        """
        # Check default language
        if "default" in settings:
            if settings["default"] not in self.supported_languages:
                raise ValidationException(f"Default language {settings['default']} is not supported")
        
        # Check enabled languages
        if "enabled" in settings:
            if not isinstance(settings["enabled"], list):
                raise ValidationException("Enabled languages must be a list")
            
            for lang in settings["enabled"]:
                if lang not in self.supported_languages:
                    raise ValidationException(f"Language {lang} is not supported")
        
        # Check auto_detect
        if "auto_detect" in settings and not isinstance(settings["auto_detect"], bool):
            raise ValidationException("auto_detect must be a boolean")
        
        # Check translations
        if "translations" in settings:
            if not isinstance(settings["translations"], dict):
                raise ValidationException("translations must be a dictionary")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_language_service = None


def get_language_service() -> LanguageService:
    """
    Get the global language service instance.
    
    Returns:
        LanguageService: Global instance
    """
    global _language_service
    
    if _language_service is None:
        _language_service = LanguageService()
    
    return _language_service
