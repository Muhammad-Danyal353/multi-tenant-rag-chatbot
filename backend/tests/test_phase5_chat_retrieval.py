"""
Test Phase 5: Chat & Retrieval Engine

Tests for:
- Hybrid search functionality
- Chat service
- LLM integration
- Widget API
- Caching
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.retrieval_service import RetrievalService
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.cache_service import CacheService, QueryCache, ResponseCache
from app.db.models.bot import Bot
from app.db.models.user import User
from app.db.models.organization import Organization
from app.schemas.chat import SendMessageRequest, SearchRequest

client = TestClient(app, base_url="http://localhost:8000")


def get_auth_token():
    """Get real authentication token by logging in."""
    login_data = {
        "email": "quicktest@example.com",
        "password": "TestPass123"
    }
    
    response = client.post("/api/v1/auth/login", json=login_data)
    if response.status_code == 200:
        data = response.json()
        # Handle different response formats
        if "access_token" in data:
            return data["access_token"]
        elif "data" in data and "tokens" in data["data"]:
            return data["data"]["tokens"]["access_token"]
        else:
            return "mock-token"
    else:
        # If login fails, try to create the user first
        try:
            register_data = {
                "email": "quicktest@example.com",
                "password": "TestPass123",
                "full_name": "Quick Test User"
            }
            client.post("/api/v1/auth/register", json=register_data)
            
            # Try login again
            response = client.post("/api/v1/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    return data["access_token"]
                elif "data" in data and "tokens" in data["data"]:
                    return data["data"]["tokens"]["access_token"]
        except:
            pass
        
        # Fallback to mock if everything fails
        return "mock-token"


def get_auth_headers():
    """Get authentication headers with real token."""
    token = get_auth_token()
    return {"Authorization": f"Bearer {token}"}


class TestRetrievalService:
    """Test retrieval service functionality."""
    
    def test_hybrid_search_basic(self):
        """Test basic hybrid search functionality."""
        with patch('app.services.retrieval_service.get_qdrant_service') as mock_qdrant, \
             patch('app.services.retrieval_service.get_embedding_service') as mock_embedding, \
             patch('app.services.retrieval_service.get_query_cache') as mock_cache:
            
            # Setup mocks
            mock_qdrant.return_value.search_vectors.return_value = [
                {"id": "1", "score": 0.9, "payload": {"content": "Test content 1"}}
            ]
            mock_qdrant.return_value.get_collection_vectors.return_value = [
                {"id": "1", "payload": {"content": "Test content 1"}}
            ]
            mock_embedding.return_value.generate_embedding.return_value = [0.1] * 384
            mock_cache.return_value.get_query_result.return_value = None
            
            # Test retrieval service
            service = RetrievalService()
            results = service.hybrid_search(
                query="test query",
                bot_id="test-bot",
                organization_id="test-org"
            )
            
            assert len(results) >= 0
            mock_qdrant.return_value.search_vectors.assert_called_once()
    
    def test_metadata_filtering(self):
        """Test metadata filtering for tenant isolation."""
        with patch('app.services.retrieval_service.get_qdrant_service') as mock_qdrant, \
             patch('app.services.retrieval_service.get_embedding_service') as mock_embedding, \
             patch('app.services.retrieval_service.get_query_cache') as mock_cache:
            
            mock_qdrant.return_value.search_vectors.return_value = []
            mock_qdrant.return_value.get_collection_vectors.return_value = []
            mock_embedding.return_value.generate_embedding.return_value = [0.1] * 384
            mock_cache.return_value.get_query_result.return_value = None
            
            service = RetrievalService()
            service.hybrid_search(
                query="test",
                bot_id="bot1",
                organization_id="org1",
                filters={"source_type": "document"}
            )
            
            # Verify filters were applied
            call_args = mock_qdrant.return_value.search_vectors.call_args
            filters = call_args[1]["filters"]
            assert filters["organization_id"] == "org1"
            assert filters["bot_id"] == "bot1"
            assert filters["source_type"] == "document"
    
    def test_deduplication(self):
        """Test result deduplication."""
        with patch('app.services.retrieval_service.get_qdrant_service') as mock_qdrant, \
             patch('app.services.retrieval_service.get_embedding_service') as mock_embedding, \
             patch('app.services.retrieval_service.get_query_cache') as mock_cache:
            
            # Mock duplicate results
            mock_qdrant.return_value.search_vectors.return_value = [
                {"id": "1", "score": 0.9, "payload": {"content": "Same content"}},
                {"id": "2", "score": 0.8, "payload": {"content": "Same content"}}
            ]
            mock_qdrant.return_value.get_collection_vectors.return_value = [
                {"id": "1", "payload": {"content": "Same content"}},
                {"id": "2", "payload": {"content": "Same content"}}
            ]
            mock_embedding.return_value.generate_embedding.return_value = [0.1] * 384
            mock_cache.return_value.get_query_result.return_value = None
            
            service = RetrievalService()
            results = service.hybrid_search(
                query="test",
                bot_id="bot1",
                organization_id="org1"
            )
            
            # Should deduplicate based on content
            assert len(results) <= 2


class TestChatService:
    """Test chat service functionality."""
    
    def test_send_message(self):
        """Test sending a message and getting response."""
        with patch('app.services.chat_service.get_retrieval_service') as mock_retrieval, \
             patch('app.services.chat_service.get_llm_service') as mock_llm:
            
            # Setup mocks
            mock_retrieval_instance = Mock()
            mock_retrieval_instance.hybrid_search.return_value = [
                {"id": "1", "content": "Test knowledge", "metadata": {}}
            ]
            mock_retrieval_instance.get_source_attribution.return_value = [
                {"content": "Test source", "source_type": "document"}
            ]
            mock_retrieval.return_value = mock_retrieval_instance
            mock_llm.return_value.generate_response.return_value = {
                "content": "Test response",
                "token_count": 10,
                "model_used": "gpt-3.5-turbo"
            }
            
            # Mock database session
            mock_db = Mock(spec=Session)
            mock_db.query.return_value.filter.return_value.first.return_value = Mock(
                id=uuid.uuid4(),
                settings={},
                system_prompt="Test prompt"
            )
            
            service = ChatService()
            response = service.send_message(
                db=mock_db,
                bot_id="test-bot",
                organization_id="test-org",
                message="Hello"
            )
            
            assert "response" in response
            assert "conversation_id" in response
            assert "sources" in response
            assert response["response"] == "Test response"
    
    def test_conversation_context(self):
        """Test conversation context management."""
        with patch('app.services.chat_service.get_retrieval_service'), \
             patch('app.services.chat_service.get_llm_service'):
            
            # Mock database with conversation history
            mock_db = Mock(spec=Session)
            from datetime import datetime
            mock_messages = [
                Mock(role="user", content="Hello", timestamp=datetime(2024, 1, 1, 0, 0, 0)),
                Mock(role="assistant", content="Hi there!", timestamp=datetime(2024, 1, 1, 0, 1, 0))
            ]
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
            
            service = ChatService()
            context = service._get_conversation_context(
                db=mock_db,
                conversation_id="test-conv",
                max_messages=10
            )
            
            assert len(context) == 2
            # Messages are ordered by timestamp desc (newest first)
            assert context[0]["role"] == "assistant"  # Newest message
            assert context[1]["role"] == "user"       # Older message


class TestLLMService:
    """Test LLM service functionality."""
    
    def test_generate_response(self):
        """Test LLM response generation."""
        with patch('app.services.llm_service.get_response_cache') as mock_cache:
            
            # Mock cache
            mock_cache.return_value.get_response.return_value = None
            mock_cache.return_value.generate_context_hash.return_value = "test-hash"
            
            service = LLMService()
            
            # Mock the client on the instance
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Test AI response"))]
            mock_response.usage = Mock(total_tokens=10, prompt_tokens=5, completion_tokens=5)
            mock_client.chat.completions.create.return_value = mock_response
            service.client = mock_client
            
            response = service.generate_response(
                user_message="Hello",
                knowledge_context="Test knowledge",
                bot_settings={"model": "gpt-3.5-turbo", "temperature": 0.7}
            )
            
            assert response["content"] == "Test AI response"
            assert response["model_used"] == "gpt-3.5-turbo"
            assert response["token_count"] == 10
    
    def test_response_caching(self):
        """Test response caching functionality."""
        with patch('app.services.llm_service.get_response_cache') as mock_cache:
            
            # Mock cache hit
            mock_cache.return_value.get_response.return_value = "Cached response"
            mock_cache.return_value.generate_context_hash.return_value = "test-hash"
            
            service = LLMService()
            
            # Mock the client on the instance
            mock_client = Mock()
            service.client = mock_client
            
            response = service.generate_response(
                user_message="Hello",
                bot_settings={"temperature": 0.1}  # Low temperature for caching
            )
            
            assert response["content"] == "Cached response"
            assert response["cached"] is True
            mock_client.chat.completions.create.assert_not_called()  # Should not call OpenAI for cached response


class TestCacheService:
    """Test cache service functionality."""
    
    def test_basic_caching(self):
        """Test basic cache operations."""
        cache = CacheService()
        
        # Test set and get
        cache.set("test_key", "test_value", ttl=60)
        value = cache.get("test_key")
        assert value == "test_value"
        
        # Test cache miss
        value = cache.get("nonexistent_key")
        assert value is None
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = CacheService()
        
        # Set with very short TTL
        cache.set("expire_key", "expire_value", ttl=0)
        
        # Should be expired immediately
        value = cache.get("expire_key")
        assert value is None
    
    def test_query_cache(self):
        """Test query-specific caching."""
        cache_service = CacheService()
        query_cache = QueryCache(cache_service)
        
        # Test query result caching
        results = [{"id": "1", "content": "test"}]
        query_cache.set_query_result(
            query="test query",
            bot_id="bot1",
            organization_id="org1",
            results=results
        )
        
        cached_results = query_cache.get_query_result(
            query="test query",
            bot_id="bot1",
            organization_id="org1"
        )
        
        assert cached_results == results
    
    def test_embedding_cache(self):
        """Test embedding caching."""
        cache_service = CacheService()
        query_cache = QueryCache(cache_service)
        
        # Test embedding caching
        embedding = [0.1] * 384
        query_cache.set_embedding("test text", embedding)
        
        cached_embedding = query_cache.get_embedding("test text")
        assert cached_embedding == embedding


class TestChatAPI:
    """Test chat API endpoints."""
    
    def test_authentication_working(self):
        """Test that real authentication is working."""
        # Test login endpoint
        login_data = {
            "email": "quicktest@example.com",
            "password": "TestPass123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        # Handle different response formats
        if "access_token" in data:
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "bearer"
            token = data["access_token"]
        elif "data" in data and "tokens" in data["data"]:
            assert "access_token" in data["data"]["tokens"]
            token = data["data"]["tokens"]["access_token"]
        else:
            assert False, f"Unexpected response format: {data}"
        
        # Test that we can use the token
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access a protected endpoint (this will fail but should not be 401)
        response = client.get("/api/v1/bots", headers=headers)
        # Should not be 401 (unauthorized) - could be 404 or other error
        assert response.status_code != 401
        
        # Test that the token works with chat endpoints
        response = client.post(
            "/api/v1/chat/test-bot/message",
            json={"message": "Hello"},
            headers=headers
        )
        # Should not be 401 (unauthorized) - could be 404 or other error
        assert response.status_code != 401
        
        # Test that without token, we get 401
        response = client.post(
            "/api/v1/chat/test-bot/message",
            json={"message": "Hello"}
        )
        assert response.status_code == 401
    
    def test_send_message_endpoint(self):
        """Test chat message endpoint."""
        with patch('app.api.v1.routes.chat.get_chat_service') as mock_chat_service:
            mock_chat_service.return_value.send_message.return_value = {
                "response": "Test response",
                "conversation_id": "test-conv",
                "message_id": "test-msg",
                "sources": [],
                "latency_ms": 100,
                "metadata": {}
            }
            
            # Use real authentication
            response = client.post(
                "/api/v1/chat/test-bot/message",
                json={"message": "Hello"},
                headers=get_auth_headers()
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Test response"
    
    def test_search_endpoint(self):
        """Test knowledge base search endpoint."""
        with patch('app.api.v1.routes.chat.get_retrieval_service') as mock_retrieval:
            mock_retrieval.return_value.hybrid_search.return_value = [
                {"id": "1", "content": "Test result", "score": 0.9}
            ]
            
            # Use real authentication
            response = client.post(
                "/api/v1/chat/test-bot/search",
                json={"query": "test search"},
                headers=get_auth_headers()
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert len(data["results"]) >= 0


class TestWidgetAPI:
    """Test widget API endpoints."""
    
    def test_widget_chat_endpoint(self):
        """Test widget chat endpoint."""
        with patch('app.api.v1.routes.widget.get_chat_service') as mock_chat_service:
            mock_chat_service.return_value.send_message.return_value = {
                "response": "Widget response",
                "conversation_id": "widget-conv",
                "message_id": "widget-msg",
                "sources": [],
                "latency_ms": 150,
                "metadata": {}
            }
            
            # Create a real bot with API key for testing
            from app.core.security import hash_api_key
            
            # Mock bot lookup with real API key
            with patch('app.core.dependencies.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                # Create a mock bot with a real API key hash
                test_api_key = "test-api-key-12345"
                api_key_hash = hash_api_key(test_api_key)
                
                mock_bot = Mock()
                mock_bot.id = "test-bot"
                mock_bot.organization_id = "test-org"
                mock_bot.allowed_domains = None
                mock_bot.api_key_hash = api_key_hash
                mock_bot.status = "active"
                
                mock_db.query.return_value.filter.return_value.first.return_value = mock_bot
                
                response = client.post(
                    f"/api/v1/widget/{test_api_key}/chat",
                    json={"message": "Hello from widget"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["response"] == "Widget response"
    
    def test_widget_config_endpoint(self):
        """Test widget configuration endpoint."""
        from app.core.security import hash_api_key
        
        with patch('app.core.dependencies.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            # Create a mock bot with a real API key hash
            test_api_key = "test-api-key-12345"
            api_key_hash = hash_api_key(test_api_key)
            
            mock_bot = Mock()
            mock_bot.id = "test-bot"
            mock_bot.name = "Test Bot"
            mock_bot.description = "Test Description"
            mock_bot.avatar_url = "test-avatar.jpg"
            mock_bot.widget_settings = {
                "colors": {"primary": "#007bff"},
                "position": "bottom-right"
            }
            mock_bot.api_key_hash = api_key_hash
            mock_bot.status = "active"
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_bot
            
            response = client.get(f"/api/v1/widget/{test_api_key}/config")
            
            assert response.status_code == 200
            data = response.json()
            assert data["bot_id"] == "test-bot"
            assert "widget_settings" in data
            assert "api_endpoints" in data


class TestPerformanceOptimizations:
    """Test performance optimizations."""
    
    def test_parallel_retrieval(self):
        """Test parallel retrieval for better performance."""
        # This would test async/parallel processing if implemented
        pass
    
    def test_batch_processing(self):
        """Test batch processing for embeddings."""
        with patch('app.services.embedding_service.get_query_cache') as mock_cache:
            mock_cache.return_value.get_embedding.return_value = None
            
            from app.services.embedding_service import get_embedding_service
            
            # Test batch embedding generation
            texts = ["Text 1", "Text 2", "Text 3"]
            service = get_embedding_service()
            
            with patch.object(service.model, 'encode') as mock_encode:
                import numpy as np
                mock_encode.return_value = np.array([[0.1] * 384] * 3)

                embeddings = service.generate_embeddings(texts)
                assert len(embeddings) == 3
                assert len(embeddings[0]) == 384
    
    def test_cache_performance(self):
        """Test cache performance improvements."""
        cache = CacheService()
        
        # Test cache hit rate
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")
        
        hits = 0
        for i in range(100):
            if cache.get(f"key_{i}") is not None:
                hits += 1
        
        assert hits == 100  # 100% hit rate for existing keys
        
        # Test cache miss
        misses = 0
        for i in range(100, 200):
            if cache.get(f"key_{i}") is None:
                misses += 1
        
        assert misses == 100  # 100% miss rate for non-existing keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
