import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from httpx import AsyncClient

from app.db.models.api_key import APIKey
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException


@pytest.mark.asyncio
async def test_create_api_key_success(client: AsyncClient, mock_auth_middleware):
    """Test successful API key creation."""
    # Setup
    bot_id = "bot123"
    data = {
        "name": "Test API Key",
        "expires_in_days": 30
    }
    
    # Mock get_bot_organization_id
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.create_api_key') as mock_create:
        
        # Setup mock return value
        api_key_obj = MagicMock(spec=APIKey)
        api_key_obj.id = "key123"
        api_key_obj.bot_id = bot_id
        api_key_obj.name = data["name"]
        api_key_obj.created_at = "2023-01-01T00:00:00Z"
        api_key_obj.expires_at = "2023-01-31T00:00:00Z"
        api_key_obj.is_active = True
        plain_key = "test_api_key_123"
        mock_create.return_value = (api_key_obj, plain_key)
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/api-keys", json=data)
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["id"] == api_key_obj.id
        assert response.json()["bot_id"] == bot_id
        assert response.json()["name"] == data["name"]
        assert response.json()["key"] == plain_key  # Should include the plain key


@pytest.mark.asyncio
async def test_create_api_key_not_found(client: AsyncClient, mock_auth_middleware):
    """Test API key creation with non-existent bot."""
    # Setup
    bot_id = "nonexistent"
    data = {"name": "Test API Key"}
    
    # Mock get_bot_organization_id to raise NotFoundException
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', side_effect=NotFoundException("Bot not found")):
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/api-keys", json=data)
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Bot not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_api_key_forbidden(client: AsyncClient, mock_auth_middleware):
    """Test API key creation with insufficient permissions."""
    # Setup
    bot_id = "bot123"
    data = {"name": "Test API Key"}
    
    # Mock get_bot_organization_id
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission', side_effect=ForbiddenException("Insufficient permissions")):
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/api-keys", json=data)
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_api_keys_success(client: AsyncClient, mock_auth_middleware):
    """Test successful API key listing."""
    # Setup
    bot_id = "bot123"
    
    # Mock API keys
    api_keys = [MagicMock(spec=APIKey) for _ in range(3)]
    for i, key in enumerate(api_keys):
        key.id = f"key{i}"
        key.bot_id = bot_id
        key.name = f"API Key {i}"
        key.created_at = "2023-01-01T00:00:00Z"
        key.expires_at = None
        key.is_active = True
        key.is_expired = lambda: False
        key.to_dict = lambda: {
            "id": key.id,
            "bot_id": key.bot_id,
            "name": key.name,
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "is_expired": False
        }
    
    # Mock get_bot_organization_id and list_api_keys
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.list_api_keys') as mock_list:
        
        # Setup mock return value
        mock_list.return_value = (api_keys, 3)
        
        # Execute
        response = await client.get(f"/api/v1/bots/{bot_id}/api-keys")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 3
        assert len(response.json()["items"]) == 3
        assert response.json()["items"][0]["id"] == "key0"


@pytest.mark.asyncio
async def test_list_api_keys_with_filters(client: AsyncClient, mock_auth_middleware):
    """Test API key listing with filters."""
    # Setup
    bot_id = "bot123"
    
    # Mock API keys
    api_keys = [MagicMock(spec=APIKey) for _ in range(2)]
    for i, key in enumerate(api_keys):
        key.id = f"key{i}"
        key.bot_id = bot_id
        key.name = f"API Key {i}"
        key.created_at = "2023-01-01T00:00:00Z"
        key.expires_at = None
        key.is_active = True
        key.is_expired = lambda: False
        key.to_dict = lambda: {
            "id": key.id,
            "bot_id": key.bot_id,
            "name": key.name,
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "is_expired": False
        }
    
    # Mock get_bot_organization_id and list_api_keys
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.list_api_keys') as mock_list:
        
        # Setup mock return value
        mock_list.return_value = (api_keys, 2)
        
        # Execute
        response = await client.get(f"/api/v1/bots/{bot_id}/api-keys?is_active=true&skip=0&limit=10")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 2
        assert len(response.json()["items"]) == 2
        
        # Verify the filter parameters were passed correctly
        mock_list.assert_awaited_once_with(
            bot_id=bot_id,
            organization_id="org123",
            is_active=True,
            skip=0,
            limit=10
        )


@pytest.mark.asyncio
async def test_revoke_api_key_success(client: AsyncClient, mock_auth_middleware):
    """Test successful API key revocation."""
    # Setup
    bot_id = "bot123"
    api_key_id = "key123"
    
    # Mock get_bot_organization_id and revoke_api_key
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.revoke_api_key') as mock_revoke:
        
        # Execute
        response = await client.delete(f"/api/v1/bots/{bot_id}/api-keys/{api_key_id}")
        
        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_revoke.assert_awaited_once_with(
            api_key_id=api_key_id,
            bot_id=bot_id,
            organization_id="org123"
        )


@pytest.mark.asyncio
async def test_revoke_api_key_not_found(client: AsyncClient, mock_auth_middleware):
    """Test API key revocation with non-existent key."""
    # Setup
    bot_id = "bot123"
    api_key_id = "nonexistent"
    
    # Mock get_bot_organization_id and revoke_api_key
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.revoke_api_key', side_effect=NotFoundException("API Key not found")):
        
        # Execute
        response = await client.delete(f"/api/v1/bots/{bot_id}/api-keys/{api_key_id}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "API Key not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_api_key_conflict(client: AsyncClient, mock_auth_middleware):
    """Test API key revocation with already inactive key."""
    # Setup
    bot_id = "bot123"
    api_key_id = "key123"
    
    # Mock get_bot_organization_id and revoke_api_key
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.revoke_api_key', side_effect=ConflictException("API Key is already inactive")):
        
        # Execute
        response = await client.delete(f"/api/v1/bots/{bot_id}/api-keys/{api_key_id}")
        
        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "API Key is already inactive" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rotate_api_key_success(client: AsyncClient, mock_auth_middleware):
    """Test successful API key rotation."""
    # Setup
    bot_id = "bot123"
    api_key_id = "key123"
    
    # Mock API key
    new_api_key = MagicMock(spec=APIKey)
    new_api_key.id = "key456"
    new_api_key.bot_id = bot_id
    new_api_key.name = "Rotated Key"
    new_api_key.created_at = "2023-01-01T00:00:00Z"
    new_api_key.expires_at = None
    new_api_key.is_active = True
    plain_key = "new_test_api_key_456"
    
    # Mock get_bot_organization_id and rotate_api_key
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.rotate_api_key') as mock_rotate:
        
        # Setup mock return value
        mock_rotate.return_value = (new_api_key, plain_key)
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/api-keys/{api_key_id}/rotate")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == new_api_key.id
        assert response.json()["bot_id"] == bot_id
        assert response.json()["name"] == "Rotated Key"
        assert response.json()["key"] == plain_key  # Should include the plain key
        
        mock_rotate.assert_awaited_once_with(
            api_key_id=api_key_id,
            bot_id=bot_id,
            organization_id="org123",
            created_by_user_id=mock_auth_middleware.return_value.id
        )


@pytest.mark.asyncio
async def test_rotate_api_key_not_found(client: AsyncClient, mock_auth_middleware):
    """Test API key rotation with non-existent key."""
    # Setup
    bot_id = "bot123"
    api_key_id = "nonexistent"
    
    # Mock get_bot_organization_id and rotate_api_key
    with patch('app.api.v1.routes.api_keys.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.api_keys.require_permission'), \
         patch('app.services.api_key_service.APIKeyService.rotate_api_key', side_effect=NotFoundException("API Key not found")):
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/api-keys/{api_key_id}/rotate")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "API Key not found" in response.json()["detail"]
