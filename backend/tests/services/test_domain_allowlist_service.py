import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.bot import Bot
from app.services.domain_allowlist_service import DomainAllowlistService
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationError
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.asyncio
async def test_get_allowed_domains_success(mock_db):
    """Test successful retrieval of allowed domains."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    allowed_domains = ["example.com", "test.com", "*.subdomain.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    bot.organization_id = organization_id
    bot.allowed_domains = allowed_domains
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.get_allowed_domains(bot_id, organization_id)
        
        # Assert
        assert result == allowed_domains


@pytest.mark.asyncio
async def test_get_allowed_domains_empty(mock_db):
    """Test retrieval of allowed domains when none are set."""
    # Setup
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = None
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.get_allowed_domains("bot123", "org123")
        
        # Assert
        assert result == []


@pytest.mark.asyncio
async def test_add_domain_success(mock_db):
    """Test successful addition of a domain."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    domain = "example.com"
    existing_domains = ["test.com"]
    expected_domains = ["test.com", "example.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    bot.organization_id = organization_id
    bot.allowed_domains = existing_domains.copy()
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot), \
         patch.object(DomainAllowlistService, '_validate_domain'):
        
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.add_domain(bot_id, organization_id, domain)
        
        # Assert
        assert result == expected_domains
        assert bot.allowed_domains == expected_domains
        mock_db.add.assert_called_once_with(bot)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(bot)


@pytest.mark.asyncio
async def test_add_domain_already_exists(mock_db):
    """Test adding a domain that already exists."""
    # Setup
    domain = "example.com"
    existing_domains = ["example.com", "test.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = existing_domains.copy()
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot), \
         patch.object(DomainAllowlistService, '_validate_domain'):
        
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.add_domain("bot123", "org123", domain)
        
        # Assert
        assert result == existing_domains
        assert bot.allowed_domains == existing_domains
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_domain_initialize_empty(mock_db):
    """Test adding a domain when allowed_domains is None."""
    # Setup
    domain = "example.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = None
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot), \
         patch.object(DomainAllowlistService, '_validate_domain'):
        
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.add_domain("bot123", "org123", domain)
        
        # Assert
        assert result == [domain]
        assert bot.allowed_domains == [domain]
        mock_db.add.assert_called_once_with(bot)
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_domain_invalid(mock_db):
    """Test adding an invalid domain."""
    # Setup
    domain = "invalid domain"
    
    # Mock _validate_domain to raise ValidationError
    with patch.object(DomainAllowlistService, '_validate_domain', side_effect=ValidationError("Invalid domain format")):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute and assert
        with pytest.raises(ValidationError):
            await service.add_domain("bot123", "org123", domain)
            
        # Verify no DB operations were performed
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_domain_success(mock_db):
    """Test successful removal of a domain."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    domain = "example.com"
    existing_domains = ["example.com", "test.com"]
    expected_domains = ["test.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    bot.organization_id = organization_id
    bot.allowed_domains = existing_domains.copy()
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.remove_domain(bot_id, organization_id, domain)
        
        # Assert
        assert result == expected_domains
        assert bot.allowed_domains == expected_domains
        mock_db.add.assert_called_once_with(bot)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(bot)


@pytest.mark.asyncio
async def test_remove_domain_not_found(mock_db):
    """Test removing a domain that doesn't exist."""
    # Setup
    domain = "nonexistent.com"
    existing_domains = ["example.com", "test.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = existing_domains.copy()
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute and assert
        with pytest.raises(NotFoundException):
            await service.remove_domain("bot123", "org123", domain)
            
        # Verify no DB operations were performed
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_domain_empty_list(mock_db):
    """Test removing a domain when allowed_domains is None."""
    # Setup
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = None
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute and assert
        with pytest.raises(NotFoundException):
            await service.remove_domain("bot123", "org123", "example.com")


@pytest.mark.asyncio
async def test_update_domains_success(mock_db):
    """Test successful update of all domains."""
    # Setup
    bot_id = "bot123"
    organization_id = "org123"
    new_domains = ["new1.com", "new2.com", "*.new3.com"]
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    bot.organization_id = organization_id
    bot.allowed_domains = ["old1.com", "old2.com"]
    
    # Mock _get_bot_with_validation
    with patch.object(DomainAllowlistService, '_get_bot_with_validation', return_value=bot), \
         patch.object(DomainAllowlistService, '_validate_domain'):
        
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute
        result = await service.update_domains(bot_id, organization_id, new_domains)
        
        # Assert
        assert result == new_domains
        assert bot.allowed_domains == new_domains
        mock_db.add.assert_called_once_with(bot)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(bot)


@pytest.mark.asyncio
async def test_update_domains_invalid(mock_db):
    """Test updating domains with an invalid domain."""
    # Setup
    new_domains = ["valid.com", "invalid domain", "another.com"]
    
    # Mock _validate_domain to raise ValidationError on the invalid domain
    def validate_side_effect(domain):
        if domain == "invalid domain":
            raise ValidationError("Invalid domain format")
    
    with patch.object(DomainAllowlistService, '_validate_domain', side_effect=validate_side_effect):
        # Service
        service = DomainAllowlistService(mock_db)
        
        # Execute and assert
        with pytest.raises(ValidationError):
            await service.update_domains("bot123", "org123", new_domains)
            
        # Verify no DB operations were performed
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_is_domain_allowed_exact_match(mock_db):
    """Test domain allowlist check with exact match."""
    # Setup
    bot_id = "bot123"
    domain = "example.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = ["example.com", "test.com"]
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is True
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_wildcard_match(mock_db):
    """Test domain allowlist check with wildcard match."""
    # Setup
    bot_id = "bot123"
    domain = "sub.example.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = ["*.example.com", "test.com"]
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is True
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_global_wildcard(mock_db):
    """Test domain allowlist check with global wildcard."""
    # Setup
    bot_id = "bot123"
    domain = "any.domain.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = ["*"]
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is True
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_no_match(mock_db):
    """Test domain allowlist check with no match."""
    # Setup
    bot_id = "bot123"
    domain = "notallowed.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = ["example.com", "*.test.com"]
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is False
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_empty_list(mock_db):
    """Test domain allowlist check with empty allowed_domains."""
    # Setup
    bot_id = "bot123"
    domain = "any.domain.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = []
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is True  # Empty list means allow all
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_none_list(mock_db):
    """Test domain allowlist check with None allowed_domains."""
    # Setup
    bot_id = "bot123"
    domain = "any.domain.com"
    
    # Mock bot
    bot = MagicMock(spec=Bot)
    bot.allowed_domains = None
    
    # Mock get
    mock_db.get.return_value = bot
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is True  # None means allow all
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


@pytest.mark.asyncio
async def test_is_domain_allowed_bot_not_found(mock_db):
    """Test domain allowlist check with non-existent bot."""
    # Setup
    bot_id = "nonexistent"
    domain = "example.com"
    
    # Mock get
    mock_db.get.return_value = None
    
    # Service
    service = DomainAllowlistService(mock_db)
    
    # Execute
    result = await service.is_domain_allowed(bot_id, domain)
    
    # Assert
    assert result is False
    mock_db.get.assert_awaited_once_with(Bot, bot_id)


def test_validate_domain_valid():
    """Test domain validation with valid domains."""
    # Setup
    service = DomainAllowlistService(None)  # DB not needed for validation
    
    # Valid domains
    valid_domains = [
        "example.com",
        "sub.example.com",
        "*.example.com",
        "example.co.uk",
        "sub.domain.example.org",
        "*"
    ]
    
    # Execute and assert
    for domain in valid_domains:
        # Should not raise an exception
        service._validate_domain(domain)


def test_validate_domain_invalid():
    """Test domain validation with invalid domains."""
    # Setup
    service = DomainAllowlistService(None)  # DB not needed for validation
    
    # Invalid domains
    invalid_domains = [
        "invalid domain",
        "example.com/path",
        "http://example.com",
        "example",
        "*.*.example.com",
        "example*.com",
        "-example.com",
        "example.com-"
    ]
    
    # Execute and assert
    for domain in invalid_domains:
        with pytest.raises(ValidationError):
            service._validate_domain(domain)
