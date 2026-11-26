import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from httpx import AsyncClient

from app.core.exceptions import NotFoundException, ValidationError, ForbiddenException


@pytest.mark.asyncio
async def test_get_allowed_domains_success(client: AsyncClient, mock_auth_middleware):
    """Test successful retrieval of allowed domains."""
    # Setup
    bot_id = "bot123"
    allowed_domains = ["example.com", "test.com", "*.subdomain.com"]
    
    # Mock get_bot_organization_id and get_allowed_domains
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.get_allowed_domains') as mock_get:
        
        # Setup mock return value
        mock_get.return_value = allowed_domains
        
        # Execute
        response = await client.get(f"/api/v1/bots/{bot_id}/domains")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == allowed_domains
        
        mock_get.assert_awaited_once_with(bot_id, "org123")


@pytest.mark.asyncio
async def test_get_allowed_domains_not_found(client: AsyncClient, mock_auth_middleware):
    """Test domain retrieval with non-existent bot."""
    # Setup
    bot_id = "nonexistent"
    
    # Mock get_bot_organization_id to raise NotFoundException
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', side_effect=NotFoundException("Bot not found")):
        # Execute
        response = await client.get(f"/api/v1/bots/{bot_id}/domains")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Bot not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_allowed_domains_forbidden(client: AsyncClient, mock_auth_middleware):
    """Test domain retrieval with insufficient permissions."""
    # Setup
    bot_id = "bot123"
    
    # Mock get_bot_organization_id and require_permission
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission', side_effect=ForbiddenException("Insufficient permissions")):
        
        # Execute
        response = await client.get(f"/api/v1/bots/{bot_id}/domains")
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_add_domain_success(client: AsyncClient, mock_auth_middleware):
    """Test successful addition of a domain."""
    # Setup
    bot_id = "bot123"
    domain = "example.com"
    updated_domains = ["example.com", "test.com"]
    
    # Mock get_bot_organization_id and add_domain
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.add_domain') as mock_add:
        
        # Setup mock return value
        mock_add.return_value = updated_domains
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/domains", json={"domain": domain})
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == updated_domains
        
        mock_add.assert_awaited_once_with(bot_id, "org123", domain)


@pytest.mark.asyncio
async def test_add_domain_validation_error(client: AsyncClient, mock_auth_middleware):
    """Test adding an invalid domain."""
    # Setup
    bot_id = "bot123"
    domain = "invalid domain"
    
    # Mock get_bot_organization_id and add_domain
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.add_domain', 
               side_effect=ValidationError("Invalid domain format")):
        
        # Execute
        response = await client.post(f"/api/v1/bots/{bot_id}/domains", json={"domain": domain})
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid domain format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_remove_domain_success(client: AsyncClient, mock_auth_middleware):
    """Test successful removal of a domain."""
    # Setup
    bot_id = "bot123"
    domain = "example.com"
    updated_domains = ["test.com"]
    
    # Mock get_bot_organization_id and remove_domain
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.remove_domain') as mock_remove:
        
        # Setup mock return value
        mock_remove.return_value = updated_domains
        
        # Execute
        response = await client.delete(f"/api/v1/bots/{bot_id}/domains/{domain}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == updated_domains
        
        mock_remove.assert_awaited_once_with(bot_id, "org123", domain)


@pytest.mark.asyncio
async def test_remove_domain_not_found(client: AsyncClient, mock_auth_middleware):
    """Test removing a non-existent domain."""
    # Setup
    bot_id = "bot123"
    domain = "nonexistent.com"
    
    # Mock get_bot_organization_id and remove_domain
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.remove_domain', 
               side_effect=NotFoundException("Domain not found")):
        
        # Execute
        response = await client.delete(f"/api/v1/bots/{bot_id}/domains/{domain}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Domain not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_domains_success(client: AsyncClient, mock_auth_middleware):
    """Test successful update of all domains."""
    # Setup
    bot_id = "bot123"
    domains = ["new1.com", "new2.com", "*.new3.com"]
    
    # Mock get_bot_organization_id and update_domains
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.update_domains') as mock_update:
        
        # Setup mock return value
        mock_update.return_value = domains
        
        # Execute
        response = await client.put(f"/api/v1/bots/{bot_id}/domains", json=domains)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == domains
        
        mock_update.assert_awaited_once_with(bot_id, "org123", domains)


@pytest.mark.asyncio
async def test_update_domains_validation_error(client: AsyncClient, mock_auth_middleware):
    """Test updating domains with an invalid domain."""
    # Setup
    bot_id = "bot123"
    domains = ["valid.com", "invalid domain", "another.com"]
    
    # Mock get_bot_organization_id and update_domains
    with patch('app.api.v1.routes.domain_allowlist.get_bot_organization_id', return_value="org123"), \
         patch('app.api.v1.routes.domain_allowlist.require_permission'), \
         patch('app.services.domain_allowlist_service.DomainAllowlistService.update_domains', 
               side_effect=ValidationError("Invalid domain format: invalid domain")):
        
        # Execute
        response = await client.put(f"/api/v1/bots/{bot_id}/domains", json=domains)
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid domain format" in response.json()["detail"]
