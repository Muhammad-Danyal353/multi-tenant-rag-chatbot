import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.invitation import Invitation
from app.db.models.organization import Organization, Membership, MemberRole
from app.db.models.user import User
from app.services.invitation_service import InvitationService
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    ForbiddenException,
    ExpiredTokenException
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.asyncio
async def test_create_invitation_success(mock_db):
    """Test successful invitation creation."""
    # Setup
    org_id = "org123"
    invited_by_user_id = "user123"
    email = "test@example.com"
    role = MemberRole.MEMBER
    
    # Mock organization
    org = MagicMock(spec=Organization)
    org.id = org_id
    org.name = "Test Org"
    mock_db.get.return_value = org
    
    # Mock existing membership check
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Mock inviter user
    inviter = MagicMock(spec=User)
    inviter.full_name = "Test User"
    
    # Service
    service = InvitationService(mock_db)
    
    # Mock token generation
    with patch('app.services.invitation_service.generate_random_string', return_value="test_token"), \
         patch('app.services.invitation_service.send_organization_invite_email', return_value=True):
        
        # Execute
        result = await service.create_invitation(org_id, invited_by_user_id, email, role)
        
        # Assert
        assert result is not None
        assert result.organization_id == org_id
        assert result.invited_by_user_id == invited_by_user_id
        assert result.email == email
        assert result.role == role
        assert result.token == "test_token"
        assert not result.is_accepted
        
        # Verify DB operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_invitation_org_not_found(mock_db):
    """Test invitation creation with non-existent organization."""
    # Setup
    mock_db.get.return_value = None
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(NotFoundException):
        await service.create_invitation("org123", "user123", "test@example.com", MemberRole.MEMBER)


@pytest.mark.asyncio
async def test_create_invitation_user_already_member(mock_db):
    """Test invitation creation when user is already a member."""
    # Setup
    org = MagicMock(spec=Organization)
    mock_db.get.return_value = org
    
    # Mock existing membership
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = MagicMock(spec=Membership)
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(ConflictException):
        await service.create_invitation("org123", "user123", "test@example.com", MemberRole.MEMBER)


@pytest.mark.asyncio
async def test_get_invitation_by_token_success(mock_db):
    """Test successful invitation retrieval by token."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = invitation
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute
    result = await service.get_invitation_by_token("test_token")
    
    # Assert
    assert result == invitation


@pytest.mark.asyncio
async def test_get_invitation_by_token_not_found(mock_db):
    """Test invitation retrieval with invalid token."""
    # Setup
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(NotFoundException):
        await service.get_invitation_by_token("invalid_token")


@pytest.mark.asyncio
async def test_accept_invitation_success(mock_db):
    """Test successful invitation acceptance."""
    # Setup
    token = "test_token"
    user_id = "user123"
    
    # Mock invitation
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = False
    invitation.organization_id = "org123"
    invitation.role = MemberRole.MEMBER
    invitation.invited_by_user_id = "inviter123"
    invitation.is_expired.return_value = False
    
    # Mock get_invitation_by_token
    with patch.object(InvitationService, 'get_invitation_by_token', return_value=invitation):
        # Mock existing membership check
        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute
        
        # Service
        service = InvitationService(mock_db)
        
        # Execute
        result = await service.accept_invitation(token, user_id)
        
        # Assert
        assert result is not None
        mock_db.add.call_count == 2  # Both membership and invitation should be added
        mock_db.commit.assert_awaited_once()
        assert invitation.is_accepted is True
        assert invitation.accepted_at is not None


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted(mock_db):
    """Test accepting an already accepted invitation."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = True
    
    # Mock get_invitation_by_token
    with patch.object(InvitationService, 'get_invitation_by_token', return_value=invitation):
        # Service
        service = InvitationService(mock_db)
        
        # Execute and assert
        with pytest.raises(ConflictException):
            await service.accept_invitation("test_token", "user123")


@pytest.mark.asyncio
async def test_accept_invitation_expired(mock_db):
    """Test accepting an expired invitation."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = False
    invitation.is_expired.return_value = True
    
    # Mock get_invitation_by_token
    with patch.object(InvitationService, 'get_invitation_by_token', return_value=invitation):
        # Service
        service = InvitationService(mock_db)
        
        # Execute and assert
        with pytest.raises(ExpiredTokenException):
            await service.accept_invitation("test_token", "user123")


@pytest.mark.asyncio
async def test_accept_invitation_already_member(mock_db):
    """Test accepting an invitation when already a member."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = False
    invitation.is_expired.return_value = False
    invitation.organization_id = "org123"
    
    # Mock get_invitation_by_token
    with patch.object(InvitationService, 'get_invitation_by_token', return_value=invitation):
        # Mock existing membership
        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = MagicMock(spec=Membership)
        mock_db.execute.return_value = mock_execute
        
        # Service
        service = InvitationService(mock_db)
        
        # Execute and assert
        with pytest.raises(ConflictException):
            await service.accept_invitation("test_token", "user123")


@pytest.mark.asyncio
async def test_list_invitations(mock_db):
    """Test listing invitations with filters."""
    # Setup
    org_id = "org123"
    invitations = [MagicMock(spec=Invitation) for _ in range(3)]
    
    # Mock count query
    mock_count_execute = AsyncMock()
    mock_count_execute.scalar_one.return_value = 3
    
    # Mock list query
    mock_list_execute = AsyncMock()
    mock_list_execute.scalars.return_value.all.return_value = invitations
    
    # Set up mock_db to return different results for different queries
    def mock_execute_side_effect(query):
        if "count" in str(query):
            return mock_count_execute
        return mock_list_execute
    
    mock_db.execute.side_effect = mock_execute_side_effect
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute
    result_invitations, total = await service.list_invitations(
        organization_id=org_id,
        is_accepted=False,
        is_expired=False
    )
    
    # Assert
    assert result_invitations == invitations
    assert total == 3
    assert mock_db.execute.call_count == 2


@pytest.mark.asyncio
async def test_revoke_invitation_success(mock_db):
    """Test successful invitation revocation."""
    # Setup
    org_id = "org123"
    invitation_id = "inv123"
    
    # Mock invitation
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = False
    invitation.is_expired.return_value = False
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = invitation
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute
    await service.revoke_invitation(org_id, invitation_id)
    
    # Assert
    assert invitation.expires_at < datetime.utcnow()
    mock_db.add.assert_called_once_with(invitation)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_invitation_not_found(mock_db):
    """Test revoking a non-existent invitation."""
    # Setup
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(NotFoundException):
        await service.revoke_invitation("org123", "inv123")


@pytest.mark.asyncio
async def test_revoke_invitation_already_accepted(mock_db):
    """Test revoking an already accepted invitation."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = True
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = invitation
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(ConflictException):
        await service.revoke_invitation("org123", "inv123")


@pytest.mark.asyncio
async def test_revoke_invitation_already_expired(mock_db):
    """Test revoking an already expired invitation."""
    # Setup
    invitation = MagicMock(spec=Invitation)
    invitation.is_accepted = False
    invitation.is_expired.return_value = True
    
    # Mock query result
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none.return_value = invitation
    mock_db.execute.return_value = mock_execute
    
    # Service
    service = InvitationService(mock_db)
    
    # Execute and assert
    with pytest.raises(ConflictException):
        await service.revoke_invitation("org123", "inv123")
