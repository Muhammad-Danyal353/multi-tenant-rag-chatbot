"""
Cache Service

Implements caching strategy for frequent queries and responses:
- Query result caching
- Embedding cache
- TTL management
- Cache invalidation
"""

import logging
import json
import hashlib
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import time

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for managing application caching.
    
    Note: This is a simple in-memory cache implementation.
    For production, consider using Redis or similar.
    """
    
    def __init__(self):
        """Initialize cache service."""
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = 3600  # 1 hour default TTL
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        entry = self.cache[key]
        
        # Check if expired
        if datetime.now() > entry["expires_at"]:
            del self.cache[key]
            self.stats["misses"] += 1
            return None
        
        self.stats["hits"] += 1
        return entry["value"]
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        self.cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now()
        }
        
        self.stats["sets"] += 1
        
        # Clean up expired entries periodically
        if len(self.cache) > 1000:  # Arbitrary limit
            self._cleanup_expired()
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        if key in self.cache:
            del self.cache[key]
            self.stats["deletes"] += 1
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "entries": len(self.cache),
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "sets": self.stats["sets"],
            "deletes": self.stats["deletes"],
            "hit_rate": round(hit_rate, 2)
        }
    
    def generate_key(
        self,
        prefix: str,
        *args: Any,
        **kwargs: Any
    ) -> str:
        """
        Generate a cache key from arguments.
        
        Args:
            prefix: Key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Generated cache key
        """
        # Create a deterministic string from arguments
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"


class QueryCache:
    """
    Specialized cache for query results.
    """
    
    def __init__(self, cache_service: CacheService):
        """Initialize query cache."""
        self.cache_service = cache_service
        self.query_ttl = 1800  # 30 minutes for query results
        self.embedding_ttl = 86400  # 24 hours for embeddings
    
    def get_query_result(
        self,
        query: str,
        bot_id: str,
        organization_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached query result.
        
        Args:
            query: Search query
            bot_id: Bot ID
            organization_id: Organization ID
            filters: Search filters
            
        Returns:
            Cached query results or None
        """
        key = self.cache_service.generate_key(
            "query",
            query=query,
            bot_id=bot_id,
            organization_id=organization_id,
            filters=filters
        )
        
        return self.cache_service.get(key)
    
    def set_query_result(
        self,
        query: str,
        bot_id: str,
        organization_id: str,
        results: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Cache query result.
        
        Args:
            query: Search query
            bot_id: Bot ID
            organization_id: Organization ID
            results: Query results
            filters: Search filters
        """
        key = self.cache_service.generate_key(
            "query",
            query=query,
            bot_id=bot_id,
            organization_id=organization_id,
            filters=filters
        )
        
        self.cache_service.set(key, results, ttl=self.query_ttl)
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding.
        
        Args:
            text: Text to get embedding for
            
        Returns:
            Cached embedding or None
        """
        key = self.cache_service.generate_key("embedding", text=text)
        return self.cache_service.get(key)
    
    def set_embedding(
        self,
        text: str,
        embedding: List[float]
    ) -> None:
        """
        Cache embedding.
        
        Args:
            text: Text
            embedding: Embedding vector
        """
        key = self.cache_service.generate_key("embedding", text=text)
        self.cache_service.set(key, embedding, ttl=self.embedding_ttl)
    
    def invalidate_bot_cache(self, bot_id: str, organization_id: str) -> None:
        """
        Invalidate all cache entries for a bot.
        
        Args:
            bot_id: Bot ID
            organization_id: Organization ID
        """
        # This is a simplified implementation
        # In production, you'd want more sophisticated cache invalidation
        keys_to_delete = []
        
        for key in self.cache_service.cache.keys():
            if f"bot_id={bot_id}" in key and f"organization_id={organization_id}" in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            self.cache_service.delete(key)
        
        logger.info(f"Invalidated {len(keys_to_delete)} cache entries for bot {bot_id}")


class ResponseCache:
    """
    Specialized cache for LLM responses.
    """
    
    def __init__(self, cache_service: CacheService):
        """Initialize response cache."""
        self.cache_service = cache_service
        self.response_ttl = 3600  # 1 hour for responses
    
    def get_response(
        self,
        user_message: str,
        context_hash: str,
        bot_id: str
    ) -> Optional[str]:
        """
        Get cached response.
        
        Args:
            user_message: User message
            context_hash: Hash of conversation context
            bot_id: Bot ID
            
        Returns:
            Cached response or None
        """
        key = self.cache_service.generate_key(
            "response",
            user_message=user_message,
            context_hash=context_hash,
            bot_id=bot_id
        )
        
        return self.cache_service.get(key)
    
    def set_response(
        self,
        user_message: str,
        context_hash: str,
        bot_id: str,
        response: str
    ) -> None:
        """
        Cache response.
        
        Args:
            user_message: User message
            context_hash: Hash of conversation context
            bot_id: Bot ID
            response: AI response
        """
        key = self.cache_service.generate_key(
            "response",
            user_message=user_message,
            context_hash=context_hash,
            bot_id=bot_id
        )
        
        self.cache_service.set(key, response, ttl=self.response_ttl)
    
    def generate_context_hash(
        self,
        context_messages: List[Dict[str, Any]],
        knowledge_context: str
    ) -> str:
        """
        Generate hash for conversation context.
        
        Args:
            context_messages: Conversation messages
            knowledge_context: Knowledge base context
            
        Returns:
            Context hash
        """
        context_data = {
            "messages": context_messages,
            "knowledge": knowledge_context
        }
        
        context_string = json.dumps(context_data, sort_keys=True)
        return hashlib.md5(context_string.encode()).hexdigest()


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create singleton instances
_cache_service: Optional[CacheService] = None
_query_cache: Optional[QueryCache] = None
_response_cache: Optional[ResponseCache] = None


def get_cache_service() -> CacheService:
    """
    Get the global cache service instance.
    
    Returns:
        CacheService: Global instance
    """
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
    
    return _cache_service


def get_query_cache() -> QueryCache:
    """
    Get the global query cache instance.
    
    Returns:
        QueryCache: Global instance
    """
    global _query_cache
    
    if _query_cache is None:
        _query_cache = QueryCache(get_cache_service())
    
    return _query_cache


def get_response_cache() -> ResponseCache:
    """
    Get the global response cache instance.
    
    Returns:
        ResponseCache: Global instance
    """
    global _response_cache
    
    if _response_cache is None:
        _response_cache = ResponseCache(get_cache_service())
    
    return _response_cache
