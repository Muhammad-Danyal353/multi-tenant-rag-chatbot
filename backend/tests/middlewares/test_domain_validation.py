import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import Request, Response
from starlette.datastructures import Headers, URL
from starlette.types import Scope

from app.core.middlewares.domain_validation import DomainValidationMiddleware
from app.db.models.bot import Bot


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    scope = {
        "type": "http",
        "headers": [
            (b"referer", b"http://example.com/page"),
            (b"x-api-key", b"test_api_key")
        ],
        "path": "/api/v1/widget/chat",
        "query_string": b""
    }
    
    request = Request(scope)
    return request


@pytest.fixture
def mock_non_widget_request():
    """Create a mock request for a non-widget endpoint."""
    scope = {
        "type": "http",
        "headers": [],
        "path": "/api/v1/auth/login",
        "query_string": b""
    }
    
    request = Request(scope)
    return request


@pytest.mark.asyncio
async def test_bypass_non_widget_endpoints():
    """Test that non-widget endpoints bypass domain validation."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[],
        path="/api/v1/auth/login",
        query_string=b""
    ))
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(status_code=200)
    
    # Execute
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assert
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_missing_api_key():
    """Test request without API key."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://example.com/page")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(status_code=200)
    
    # Execute
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assert
    assert response.status_code == 401
    response_json = await response.json()
    assert "API key is required" in response_json["error"]


@pytest.mark.asyncio
async def test_missing_referer():
    """Test request without referer header."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"x-api-key", b"test_api_key")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(status_code=200)
    
    # Execute
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assert
    assert response.status_code == 403
    response_json = await response.json()
    assert "Referer header is required" in response_json["error"]


@pytest.mark.asyncio
async def test_invalid_api_key():
    """Test request with invalid API key."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://example.com/page"),
            (b"x-api-key", b"invalid_api_key")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock get_db_session and validate_api_key
    with patch('app.core.middlewares.domain_validation.get_db_session') as mock_get_db, \
         patch('app.services.api_key_service.APIKeyService.validate_api_key') as mock_validate:
        
        # Setup mock DB session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db_session
        
        # Setup mock validate_api_key to return None (invalid key)
        mock_validate.return_value = None
        
        # Mock call_next
        async def mock_call_next(request):
            return Response(status_code=200)
        
        # Execute
        response = await middleware.dispatch(request, mock_call_next)
        
        # Assert
        assert response.status_code == 401
        response_json = await response.json()
        assert "Invalid API key" in response_json["error"]


@pytest.mark.asyncio
async def test_domain_not_allowed():
    """Test request from a domain that is not allowed."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://notallowed.com/page"),
            (b"x-api-key", b"test_api_key")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock bot and domain validation
    bot = MagicMock(spec=Bot)
    bot.id = "bot123"
    bot.organization_id = "org123"
    
    # Mock get_db_session, validate_api_key, and is_domain_allowed
    with patch('app.core.middlewares.domain_validation.get_db_session') as mock_get_db, \
         patch('app.services.api_key_service.APIKeyService.validate_api_key') as mock_validate, \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.is_domain_allowed') as mock_is_allowed:
        
        # Setup mock DB session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db_session
        
        # Setup mock validate_api_key to return a bot
        mock_validate.return_value = bot
        
        # Setup mock is_domain_allowed to return False
        mock_is_allowed.return_value = False
        
        # Mock call_next
        async def mock_call_next(request):
            return Response(status_code=200)
        
        # Execute
        response = await middleware.dispatch(request, mock_call_next)
        
        # Assert
        assert response.status_code == 403
        response_json = await response.json()
        assert "Domain 'notallowed.com' is not allowed" in response_json["error"]


@pytest.mark.asyncio
async def test_domain_allowed_success():
    """Test successful request from an allowed domain."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://allowed.com/page"),
            (b"x-api-key", b"test_api_key")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock bot and domain validation
    bot = MagicMock(spec=Bot)
    bot.id = "bot123"
    bot.organization_id = "org123"
    
    # Mock get_db_session, validate_api_key, and is_domain_allowed
    with patch('app.core.middlewares.domain_validation.get_db_session') as mock_get_db, \
         patch('app.services.api_key_service.APIKeyService.validate_api_key') as mock_validate, \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.is_domain_allowed') as mock_is_allowed:
        
        # Setup mock DB session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db_session
        
        # Setup mock validate_api_key to return a bot
        mock_validate.return_value = bot
        
        # Setup mock is_domain_allowed to return True
        mock_is_allowed.return_value = True
        
        # Mock call_next
        async def mock_call_next(request):
            return Response(status_code=200, content="Success")
        
        # Execute
        response = await middleware.dispatch(request, mock_call_next)
        
        # Assert
        assert response.status_code == 200
        assert request.state.bot_id == "bot123"
        assert request.state.organization_id == "org123"


@pytest.mark.asyncio
async def test_domain_with_port():
    """Test request from a domain with port number."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://example.com:8080/page"),
            (b"x-api-key", b"test_api_key")
        ],
        path="/api/v1/widget/chat",
        query_string=b""
    ))
    
    # Mock bot and domain validation
    bot = MagicMock(spec=Bot)
    bot.id = "bot123"
    bot.organization_id = "org123"
    
    # Mock get_db_session, validate_api_key, and is_domain_allowed
    with patch('app.core.middlewares.domain_validation.get_db_session') as mock_get_db, \
         patch('app.services.api_key_service.APIKeyService.validate_api_key') as mock_validate, \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.is_domain_allowed') as mock_is_allowed:
        
        # Setup mock DB session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db_session
        
        # Setup mock validate_api_key to return a bot
        mock_validate.return_value = bot
        
        # Setup mock is_domain_allowed to return True
        mock_is_allowed.return_value = True
        
        # Mock call_next
        async def mock_call_next(request):
            return Response(status_code=200)
        
        # Execute
        response = await middleware.dispatch(request, mock_call_next)
        
        # Assert
        assert response.status_code == 200
        # Verify that the port was stripped from the domain
        mock_is_allowed.assert_awaited_once_with("bot123", "example.com")


@pytest.mark.asyncio
async def test_api_key_from_query_param():
    """Test request with API key in query parameter."""
    # Setup
    middleware = DomainValidationMiddleware()
    request = Request(Scope(
        type="http",
        headers=[
            (b"referer", b"http://example.com/page")
        ],
        path="/api/v1/widget/chat",
        query_string=b"api_key=test_api_key"
    ))
    
    # Mock bot and domain validation
    bot = MagicMock(spec=Bot)
    bot.id = "bot123"
    bot.organization_id = "org123"
    
    # Mock get_db_session, validate_api_key, and is_domain_allowed
    with patch('app.core.middlewares.domain_validation.get_db_session') as mock_get_db, \
         patch('app.services.api_key_service.APIKeyService.validate_api_key') as mock_validate, \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.is_domain_allowed') as mock_is_allowed:
        
        # Setup mock DB session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db_session
        
        # Setup mock validate_api_key to return a bot
        mock_validate.return_value = bot
        
        # Setup mock is_domain_allowed to return True
        mock_is_allowed.return_value = True
        
        # Mock call_next
        async def mock_call_next(request):
            return Response(status_code=200)
        
        # Execute
        response = await middleware.dispatch(request, mock_call_next)
        
        # Assert
        assert response.status_code == 200
        mock_validate.assert_awaited_once_with("test_api_key")
