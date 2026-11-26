import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.api_key import APIKey
from app.db.models.bot import Bot
from app.services.api_key_service import APIKeyService
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    ForbiddenException
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.asyncio
async def test_create_api_key_success(mock_db):
    """Test successful API key creation."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    created_by_user_id = "user123"
    name = "Test API Key"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    bot.organization_id = organization_id
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = bot
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Mock key generation
    with patch('app.services.api_key_service.generate_api_key', return_value="test_api_key"), \
         patch('app.services.api_key_service.hash_api_key', return_value="hashed_key"):
        
        # Execute
        api_key_obj, plain_key = await service.create_api_key(
            bot_id=bot_id,
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            name=name
        )
        
        # Assert
        assert api_key_obj is not None
        assert api_key_obj.bot_id == bot_id
        assert api_key_obj.organization_id == organization_id
        assert api_key_obj.created_by_user_id == created_by_user_id
        assert api_key_obj.name == name
        assert api_key_obj.key_hash == "hashed_key"
        assert api_key_obj.is_active is True
        assert plain_key == "test_api_key"
        
        # Verify DB operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_api_key_bot_not_found(mock_db):
    """Test API key creation with non-existent bot."""
    # Setup
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Execute and assert
    with pytest.raises(NotFoundException):
        await service.create_api_key(
            bot_id="bot123",
            organization_id="org123",
            created_by_user_id="user123"
        )


@pytest.mark.asyncio
async def test_list_api_keys(mock_db):
    """Test listing API keys with filters."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    api_keys = [MagicMock(spec=APIKey) for _ in range(3)]
    
    # Mock count query
    mock_count_execute = AsyncMock()
    mock_count_execute.scalar_one.return_value = 3
    
    # Mock list query
    mock_list_execute = AsyncMock()
    mock_list_execute.scalars.return_value.all.return_value = api_keys
    
    # Set up mock_db to return different results for different queries
    def mock_execute_side_effect(query):
        if "count" in str(query):
            return mock_count_execute
        return mock_list_execute
    
    mock_db.execute.side_effect = mock_execute_side_effect
    
    # Service
    service = APIKeyService(mock_db)
    
    # Execute
    result_keys, total = await service.list_api_keys(
        bot_id=bot_id,
        organization_id=organization_id,
        is_active=True
    )
    
    # Assert
    assert result_keys == api_keys
    assert total == 3
    assert mock_db.execute.call_count == 2


@pytest.mark.asyncio
async def test_revoke_api_key_success(mock_db):
    """Test successful API key revocation."""
    # Setup
    api_key_id = "key123"
    bot_id = "bot123"
    organization_id = "org123"
    
    # Mock API key
    api_key = MagicMock(spec=APIKey)
    api_key.id = api_key_id
    api_key.bot_id = bot_id
    api_key.organization_id = organization_id
    api_key.is_active = True
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = api_key
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Execute
    await service.revoke_api_key(api_key_id, bot_id, organization_id)
    
    # Assert
    assert api_key.is_active is False
    assert api_key.revoked_at is not None
    mock_db.add.assert_called_once_with(api_key)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_api_key_not_found(mock_db):
    """Test revoking a non-existent API key."""
    # Setup
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Execute and assert
    with pytest.raises(NotFoundException):
        await service.revoke_api_key("key123", "bot123", "org123")


@pytest.mark.asyncio
async def test_revoke_api_key_already_inactive(mock_db):
    """Test revoking an already inactive API key."""
    # Setup
    api_key = MagicMock(spec=APIKey)
    api_key.is_active = False
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = api_key
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Execute and assert
    with pytest.raises(ConflictException):
        await service.revoke_api_key("key123", "bot123", "org123")


@pytest.mark.asyncio
async def test_rotate_api_key_success(mock_db):
    """Test successful API key rotation."""
    # Setup
    api_key_id = "key123"
    bot_id = "bot123"
    organization_id = "org123"
    created_by_user_id = "user123"
    
    # Mock revoke_api_key
    with patch.object(APIKeyService, 'revoke_api_key') as mock_revoke, \
         patch.object(APIKeyService, 'create_api_key') as mock_create:
        
        # Setup mock create_api_key return value
        new_api_key = MagicMock(spec=APIKey)
        new_plain_key = "new_test_api_key"
        mock_create.return_value = (new_api_key, new_plain_key)
        
        # Service
        service = APIKeyService(mock_db)
        
        # Execute
        result_key, result_plain_key = await service.rotate_api_key(
            api_key_id=api_key_id,
            bot_id=bot_id,
            organization_id=organization_id,
            created_by_user_id=created_by_user_id
        )
        
        # Assert
        mock_revoke.assert_awaited_once_with(api_key_id, bot_id, organization_id)
        mock_create.assert_awaited_once()
        assert result_key == new_api_key
        assert result_plain_key == new_plain_key


@pytest.mark.asyncio
async def test_validate_api_key_success(mock_db):
    """Test successful API key validation."""
    # Setup
    plain_key = "test_api_key"
    
    # Mock API key
    api_key = MagicMock(spec=APIKey)
    api_key.bot_id = "bot123"
    api_key.is_active = True
    api_key.expires_at = None
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.status = "active"
    
    # Mock query result for API key
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = api_key
    mock_db.execute.return_value = mock_execute
    
    # Mock get for bot
    mock_db.get.return_value = bot
    
    # Service
    service = APIKeyService(mock_db)
    
    # Mock hash_api_key
    with patch('app.services.api_key_service.hash_api_key', return_value="hashed_key"):
        # Execute
        result = await service.validate_api_key(plain_key)
        
        # Assert
        assert result == bot
        mock_db.get.assert_awaited_once_with(Bot, api_key.bot_id)


@pytest.mark.asyncio
async def test_validate_api_key_not_found(mock_db):
    """Test API key validation with non-existent key."""
    # Setup
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Mock hash_api_key
    with patch('app.services.api_key_service.hash_api_key', return_value="hashed_key"):
        # Execute
        result = await service.validate_api_key("test_api_key")
        
        # Assert
        assert result is None


@pytest.mark.asyncio
async def test_validate_api_key_expired(mock_db):
    """Test API key validation with expired key."""
    # Setup
    api_key = MagicMock(spec=APIKey)
    api_key.is_active = True
    api_key.expires_at = datetime.utcnow() - timedelta(days=1)  # Expired
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = api_key
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = APIKeyService(mock_db)
    
    # Mock hash_api_key
    with patch('app.services.api_key_service.hash_api_key', return_value="hashed_key"):
        # Execute
        result = await service.validate_api_key("test_api_key")
        
        # Assert
        assert result is None


@pytest.mark.asyncio
async def test_validate_api_key_inactive_bot(mock_db):
    """Test API key validation with inactive bot."""
    # Setup
    api_key = MagicMock(spec=APIKey)
    api_key.bot_id = "bot123"
    api_key.is_active = True
    api_key.expires_at = None
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.status = "inactive"  # Inactive bot
    
    # Mock query result for API key
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = api_key
    mock_db.execute.return_value = mock_execute
    
    # Mock get for bot
    mock_db.get.return_value = bot
    
    # Service
    service = APIKeyService(mock_db)
    
    # Mock hash_api_key
    with patch('app.services.api_key_service.hash_api_key', return_value="hashed_key"):
        # Execute
        result = await service.validate_api_key("test_api_key")
        
        # Assert
        assert result is None
