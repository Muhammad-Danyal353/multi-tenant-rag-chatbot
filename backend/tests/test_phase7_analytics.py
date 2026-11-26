"""
Tests for Phase 7: Analytics & Monitoring

This module contains tests for the analytics, conversation management,
and monitoring features implemented in Phase 7.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.models.event import Event
from app.db.models.conversation import Conversation, Message
from app.db.models.audit_log import AuditLog
from app.services.analytics_service import get_analytics_service
from app.services.audit_service import get_audit_service


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = MagicMock(spec=AsyncSession)
    
    # Mock execute method to return query results
    async def mock_execute(*args, **kwargs):
        result = MagicMock()
        
        # Mock scalar_one or scalar_one_or_none methods
        result.scalar_one = MagicMock(return_value=10)
        result.scalar_one_or_none = MagicMock(return_value=10)
        
        # Mock scalars method
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result.scalars = MagicMock(return_value=scalars)
        
        # Mock fetchone and fetchall methods
        result.fetchone = MagicMock(return_value=MagicMock(
            total=10, positive=8, negative=1, average=4.5,
            total_messages=100, messages_with_sources=80
        ))
        result.fetchall = MagicMock(return_value=[])
        
        return result
    
    session.execute = mock_execute
    
    # Mock commit method
    async def mock_commit():
        return None
    
    session.commit = mock_commit
    
    # Mock add method
    def mock_add(obj):
        return None
    
    session.add = mock_add
    
    return session


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def mock_auth_headers():
    """Mock authentication headers for testing."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_event():
    """Mock event for testing."""
    return Event(
        id="test_event_id",
        organization_id="test_org_id",
        event_type="test_event",
        event_data={"key": "value"},
        timestamp=datetime.utcnow()
    )


@pytest.fixture
def mock_conversation():
    """Mock conversation for testing."""
    return Conversation(
        id="test_conversation_id",
        organization_id="test_org_id",
        bot_id="test_bot_id",
        session_id="test_session_id",
        started_at=datetime.utcnow() - timedelta(minutes=10),
        ended_at=datetime.utcnow(),
        duration=600,  # 10 minutes
        rating=4,
        feedback="Great service!"
    )


@pytest.fixture
def mock_message():
    """Mock message for testing."""
    return Message(
        id="test_message_id",
        conversation_id="test_conversation_id",
        role="user",
        content="Hello, how can I help?",
        timestamp=datetime.utcnow(),
        latency_ms=150,
        token_count=10
    )


@pytest.fixture
def mock_audit_log():
    """Mock audit log for testing."""
    return AuditLog(
        id="test_audit_log_id",
        organization_id="test_org_id",
        user_id="test_user_id",
        action="create",
        resource_type="bot",
        resource_id="test_bot_id",
        changes={"name": {"old": None, "new": "Test Bot"}},
        ip_address="127.0.0.1",
        timestamp=datetime.utcnow()
    )


class TestAnalyticsService:
    """Tests for the analytics service."""
    
    @pytest.mark.asyncio
    @patch("app.services.analytics_service.select")
    async def test_get_overview_metrics(self, mock_select, mock_db_session):
        """Test getting overview metrics."""
        # Arrange
        analytics_service = get_analytics_service()
        organization_id = "test_org_id"
        
        # Act
        metrics = await analytics_service.get_overview_metrics(
            organization_id=organization_id,
            db=mock_db_session
        )
        
        # Assert
        assert "total_conversations" in metrics
        assert "total_messages" in metrics
        assert "avg_messages_per_conversation" in metrics
        assert "avg_response_time_ms" in metrics
        assert "satisfaction_score" in metrics
        assert "conversation_trend" in metrics
        assert "date_range" in metrics
    
    @pytest.mark.asyncio
    @patch("app.services.analytics_service.select")
    async def test_get_conversation_analytics(self, mock_select, mock_db_session):
        """Test getting conversation analytics."""
        # Arrange
        analytics_service = get_analytics_service()
        organization_id = "test_org_id"
        
        # Act
        analytics = await analytics_service.get_conversation_analytics(
            organization_id=organization_id,
            db=mock_db_session
        )
        
        # Assert
        assert "total_conversations" in analytics
        assert "avg_duration_seconds" in analytics
        assert "rated_conversations" in analytics
        assert "avg_rating" in analytics
        assert "duration_distribution" in analytics
        assert "volume_by_hour" in analytics
        assert "top_queries" in analytics
        assert "date_range" in analytics
    
    @pytest.mark.asyncio
    @patch("app.services.analytics_service.select")
    async def test_get_source_analytics(self, mock_select, mock_db_session):
        """Test getting source analytics."""
        # Arrange
        analytics_service = get_analytics_service()
        organization_id = "test_org_id"
        
        # Act
        analytics = await analytics_service.get_source_analytics(
            organization_id=organization_id,
            db=mock_db_session
        )
        
        # Assert
        assert "source_usage" in analytics
        assert "source_coverage" in analytics
        assert "date_range" in analytics
    
    @pytest.mark.asyncio
    @patch("app.services.analytics_service.Event")
    async def test_track_event(self, mock_event_class, mock_db_session):
        """Test tracking an event."""
        # Arrange
        analytics_service = get_analytics_service()
        organization_id = "test_org_id"
        event_type = "test_event"
        event_data = {"key": "value"}
        
        # Mock the Event instance
        mock_event = MagicMock()
        mock_event.organization_id = organization_id
        mock_event.event_type = event_type
        mock_event.event_data = event_data
        mock_event_class.return_value = mock_event
        
        # Act
        event = await analytics_service.track_event(
            organization_id=organization_id,
            event_type=event_type,
            event_data=event_data,
            db=mock_db_session
        )
        
        # Assert
        assert event.organization_id == organization_id
        assert event.event_type == event_type
        assert event.event_data == event_data
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestAuditService:
    """Tests for the audit service."""
    
    @pytest.mark.asyncio
    @patch("app.services.audit_service.AuditLog")
    async def test_log_action(self, mock_audit_log_class, mock_db_session):
        """Test logging an action."""
        # Arrange
        audit_service = get_audit_service()
        organization_id = "test_org_id"
        user_id = "test_user_id"
        action = "create"
        resource_type = "bot"
        resource_id = "test_bot_id"
        changes = {"name": {"old": None, "new": "Test Bot"}}
        
        # Mock the AuditLog instance
        mock_audit_log = MagicMock()
        mock_audit_log.organization_id = organization_id
        mock_audit_log.user_id = user_id
        mock_audit_log.action = action
        mock_audit_log.resource_type = resource_type
        mock_audit_log.resource_id = resource_id
        mock_audit_log.changes = changes
        mock_audit_log_class.return_value = mock_audit_log
        
        # Act
        audit_log = await audit_service.log_action(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            db=mock_db_session
        )
        
        # Assert
        assert audit_log.organization_id == organization_id
        assert audit_log.user_id == user_id
        assert audit_log.action == action
        assert audit_log.resource_type == resource_type
        assert audit_log.resource_id == resource_id
        assert audit_log.changes == changes
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.audit_service.select")
    async def test_get_audit_logs(self, mock_select, mock_db_session):
        """Test getting audit logs."""
        # Arrange
        audit_service = get_audit_service()
        organization_id = "test_org_id"
        
        # Act
        logs = await audit_service.get_audit_logs(
            organization_id=organization_id,
            db=mock_db_session
        )
        
        # Assert
        assert "items" in logs
        assert "total" in logs
        assert "page" in logs
        assert "page_size" in logs
        assert "has_more" in logs
    
    @pytest.mark.asyncio
    @patch("app.services.audit_service.select")
    async def test_get_user_activity(self, mock_select, mock_db_session):
        """Test getting user activity."""
        # Arrange
        audit_service = get_audit_service()
        organization_id = "test_org_id"
        user_id = "test_user_id"
        
        # Act
        activity = await audit_service.get_user_activity(
            organization_id=organization_id,
            user_id=user_id,
            db=mock_db_session
        )
        
        # Assert
        assert isinstance(activity, list)
    
    @pytest.mark.asyncio
    @patch("app.services.audit_service.select")
    async def test_get_resource_history(self, mock_select, mock_db_session):
        """Test getting resource history."""
        # Arrange
        audit_service = get_audit_service()
        organization_id = "test_org_id"
        resource_type = "bot"
        resource_id = "test_bot_id"
        
        # Act
        history = await audit_service.get_resource_history(
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            db=mock_db_session
        )
        
        # Assert
        assert isinstance(history, list)


@pytest.mark.parametrize(
    "endpoint,expected_status,expected_keys",
    [
        ("/api/v1/analytics/overview/test_org_id", 200, ["total_conversations", "total_messages"]),
        ("/api/v1/analytics/conversations/test_org_id", 200, ["total_conversations", "avg_duration_seconds"]),
        ("/api/v1/analytics/sources/test_org_id", 200, ["source_usage", "source_coverage"]),
        ("/health", 200, ["status"]),
        ("/health/detailed", 200, ["status", "components"]),
        ("/health/metrics", 200, None),  # Metrics returns plain text
    ]
)
@patch("app.core.dependencies.get_current_user")
@patch("app.core.dependencies.require_permission")
@patch("app.api.v1.routes.analytics.get_analytics_service")
@patch("app.core.dependencies.get_db")
def test_analytics_endpoints(
    mock_get_db, mock_get_analytics_service, mock_require_permission, 
    mock_get_current_user, endpoint, expected_status, expected_keys, 
    client, mock_db_session, mock_auth_headers
):
    """Test analytics endpoints."""
    # Arrange
    mock_get_db.return_value = mock_db_session
    mock_get_current_user.return_value = {"id": "test_user_id", "email": "test@example.com"}
    mock_require_permission.return_value = None
    
    analytics_service = MagicMock()
    analytics_service.get_overview_metrics.return_value = {
        "total_conversations": 100,
        "total_messages": 500,
        "avg_messages_per_conversation": 5.0,
        "avg_response_time_ms": 150.0,
        "satisfaction_score": 85,
        "conversation_trend": [],
        "date_range": {"start": "2023-01-01", "end": "2023-01-31"}
    }
    analytics_service.get_conversation_analytics.return_value = {
        "total_conversations": 100,
        "avg_duration_seconds": 120.5,
        "rated_conversations": 80,
        "avg_rating": 4.5,
        "duration_distribution": [],
        "volume_by_hour": [],
        "top_queries": [],
        "date_range": {"start": "2023-01-01", "end": "2023-01-31"}
    }
    analytics_service.get_source_analytics.return_value = {
        "source_usage": [],
        "source_coverage": {
            "total_messages": 500,
            "messages_with_sources": 450,
            "coverage_percentage": 90.0
        },
        "date_range": {"start": "2023-01-01", "end": "2023-01-31"}
    }
    mock_get_analytics_service.return_value = analytics_service
    
    # Act
    response = client.get(endpoint, headers=mock_auth_headers)
    
    # Assert
    assert response.status_code == expected_status
    
    if expected_keys:
        response_json = response.json()
        for key in expected_keys:
            assert key in response_json


@pytest.mark.parametrize(
    "endpoint,expected_status,expected_keys",
    [
        ("/api/v1/conversations/test_org_id", 200, ["items", "total"]),
        ("/api/v1/conversations/test_org_id/test_conversation_id", 200, ["id", "messages"]),
        ("/api/v1/audit/test_org_id", 200, ["items", "total"]),
        ("/api/v1/audit/test_org_id/users/test_user_id/activity", 200, ["items"]),
        ("/api/v1/audit/test_org_id/resources/bot/test_bot_id/history", 200, ["items"]),
    ]
)
@patch("app.core.dependencies.get_current_user")
@patch("app.core.dependencies.require_permission")
@patch("app.api.v1.routes.audit.get_audit_service")
@patch("app.core.dependencies.get_db")
def test_management_endpoints(
    mock_get_db, mock_get_audit_service, mock_require_permission,
    mock_get_current_user, endpoint, expected_status, expected_keys, 
    client, mock_db_session, mock_auth_headers
):
    """Test conversation management and audit endpoints."""
    # Arrange
    mock_get_db.return_value = mock_db_session
    mock_get_current_user.return_value = {"id": "test_user_id", "email": "test@example.com"}
    mock_require_permission.return_value = None
    
    audit_service = MagicMock()
    audit_service.get_audit_logs.return_value = {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "has_more": False
    }
    audit_service.get_user_activity.return_value = []
    audit_service.get_resource_history.return_value = []
    mock_get_audit_service.return_value = audit_service
    
    # Mock select to return empty results
    with patch("sqlalchemy.future.select", return_value=MagicMock()):
        # Act
        response = client.get(endpoint, headers=mock_auth_headers)
    
    # Assert
    assert response.status_code == expected_status
    
    if expected_keys:
        response_json = response.json()
        for key in expected_keys:
            assert key in response_json


@pytest.mark.asyncio
@patch("app.core.health_checks.check_database_connection")
@patch("app.core.health_checks.check_qdrant_connection")
@patch("app.core.health_checks.check_openai_connection")
@patch("app.core.health_checks.check_system_resources")
async def test_health_checks(
    mock_system_resources, mock_openai_connection,
    mock_qdrant_connection, mock_db_connection
):
    """Test health check functions."""
    # Arrange
    mock_db_connection.return_value = {
        "status": "healthy",
        "latency_ms": 5.2,
        "error": None,
        "version": "PostgreSQL 13.4"
    }
    
    mock_qdrant_connection.return_value = {
        "status": "healthy",
        "latency_ms": 10.5,
        "error": None,
        "collections": ["test_collection"]
    }
    
    mock_openai_connection.return_value = {
        "status": "healthy",
        "latency_ms": 250.3,
        "error": None
    }
    
    mock_system_resources.return_value = {
        "cpu": {"percent": 25.5},
        "memory": {"percent": 60.2, "used_mb": 4096, "total_mb": 8192},
        "disk": {"percent": 45.8, "used_gb": 100, "total_gb": 500},
        "process": {"memory_mb": 256, "cpu_percent": 5.2, "threads": 8}
    }
    
    # Act
    from app.core.health_checks import get_basic_health, get_detailed_health
    basic_health = await get_basic_health()
    detailed_health = await get_detailed_health(MagicMock())
    
    # Assert
    assert basic_health["status"] == "ok"
    assert detailed_health["status"] == "healthy"
    assert "components" in detailed_health
    assert "database" in detailed_health["components"]
    assert "qdrant" in detailed_health["components"]
    assert "openai" in detailed_health["components"]
    assert "system" in detailed_health
