"""
Tests for Lemon Squeezy Integration

This module contains tests for the Lemon Squeezy billing integration.
"""

import pytest
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.models.subscription import Subscription, Plan
from app.db.models.organization import Organization
from app.services.billing_service import get_billing_service, BillingService
from app.services.checkout_service import get_checkout_service, CheckoutService
from app.services.usage_service import get_usage_service, UsageService


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = MagicMock(spec=AsyncSession)
    
    # Mock execute method to return query results
    async def mock_execute(query):
        result = MagicMock()
        
        # Mock scalar_one or scalar_one_or_none methods
        result.scalar_one = MagicMock(return_value=10)
        result.scalar_one_or_none = MagicMock(return_value=None)
        
        # Mock scalars method
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result.scalars = MagicMock(return_value=scalars)
        
        # Mock fetchone and fetchall methods
        result.fetchone = MagicMock(return_value=None)
        result.fetchall = MagicMock(return_value=[])
        
        return result
    
    session.execute = mock_execute
    
    # Mock commit method
    async def mock_commit():
        return None
    
    session.commit = mock_commit
    
    # Mock rollback method
    async def mock_rollback():
        return None
    
    session.rollback = mock_rollback
    
    # Mock add method
    def mock_add(obj):
        return None
    
    session.add = mock_add
    
    return session


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_auth_headers():
    """Mock authentication headers for testing."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_subscription():
    """Mock subscription for testing."""
    return Subscription(
        id="test_subscription_id",
        organization_id="test_org_id",
        plan_id="pro",
        status="active",
        lemonsqueezy_subscription_id="ls_sub_123456",
        current_period_start=datetime.utcnow().isoformat(),
        current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
    )


@pytest.fixture
def mock_organization():
    """Mock organization for testing."""
    return Organization(
        id="test_org_id",
        name="Test Organization",
        subscription_plan="pro",
        subscription_status="active"
    )


@pytest.fixture
def mock_plan():
    """Mock plan for testing."""
    return Plan(
        id="pro",
        name="Pro Plan",
        slug="pro",
        price=29.0,
        features={"feature_list": ["5 bots", "1,000 messages/month"]},
        limits={
            "max_bots": 5,
            "max_messages_per_month": 1000,
            "max_storage_mb": 500,
            "max_knowledge_sources": 50
        },
        payment_provider="lemonsqueezy",
        payment_price_id="ls_variant_123456"
    )


@pytest.fixture
def mock_webhook_payload():
    """Mock webhook payload for testing."""
    return {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "organization_id": "test_org_id",
                "user_id": "test_user_id"
            }
        },
        "data": {
            "id": "ls_sub_123456",
            "type": "subscriptions",
            "attributes": {
                "status": "active",
                "variant_id": "ls_variant_123456",
                "renews_at": datetime.utcnow().isoformat(),
                "ends_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        }
    }


class TestBillingService:
    """Tests for the billing service."""
    
    @pytest.mark.asyncio
    @patch("app.services.billing_service.httpx.AsyncClient")
    async def test_create_checkout(self, mock_client):
        """Test creating a checkout session."""
        # Arrange
        billing_service = BillingService()
        billing_service.api_key = "test_api_key"
        billing_service.store_id = "test_store_id"
        billing_service.pro_variant_id = "ls_variant_123456"
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "id": "ls_checkout_123456",
                "attributes": {
                    "url": "https://checkout.lemonsqueezy.com/123456",
                    "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat()
                }
            }
        }
        
        # Mock AsyncClient
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Act
        checkout = await billing_service.create_checkout(
            variant_id="ls_variant_123456",
            user_email="test@example.com",
            custom_data={"organization_id": "test_org_id"}
        )
        
        # Assert
        assert checkout["checkout_id"] == "ls_checkout_123456"
        assert checkout["checkout_url"] == "https://checkout.lemonsqueezy.com/123456"
        assert "expires_at" in checkout
        mock_client_instance.post.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.billing_service.httpx.AsyncClient")
    async def test_get_subscription(self, mock_client):
        """Test getting subscription details."""
        # Arrange
        billing_service = BillingService()
        billing_service.api_key = "test_api_key"
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "ls_sub_123456",
                "attributes": {
                    "status": "active",
                    "renews_at": datetime.utcnow().isoformat(),
                    "ends_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
                }
            }
        }
        
        # Mock AsyncClient
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Act
        subscription = await billing_service.get_subscription("ls_sub_123456")
        
        # Assert
        assert subscription["data"]["id"] == "ls_sub_123456"
        assert subscription["data"]["attributes"]["status"] == "active"
        mock_client_instance.get.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.billing_service.httpx.AsyncClient")
    async def test_cancel_subscription(self, mock_client):
        """Test cancelling a subscription."""
        # Arrange
        billing_service = BillingService()
        billing_service.api_key = "test_api_key"
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "ls_sub_123456",
                "attributes": {
                    "status": "cancelled"
                }
            }
        }
        
        # Mock AsyncClient
        mock_client_instance = AsyncMock()
        mock_client_instance.delete.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Act
        result = await billing_service.cancel_subscription("ls_sub_123456")
        
        # Assert
        assert result["data"]["id"] == "ls_sub_123456"
        assert result["data"]["attributes"]["status"] == "cancelled"
        mock_client_instance.delete.assert_called_once()
    
    def test_verify_webhook_signature(self):
        """Test webhook signature verification."""
        # Arrange
        billing_service = BillingService()
        billing_service.webhook_secret = "test_webhook_secret"
        
        # Create payload and signature
        payload = json.dumps({"test": "data"}).encode()
        signature = hmac.new(
            key=b"test_webhook_secret",
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Act
        is_valid = billing_service.verify_webhook_signature(payload, signature)
        
        # Assert
        assert is_valid is True
        
        # Test invalid signature
        invalid_signature = "invalid_signature"
        is_valid = billing_service.verify_webhook_signature(payload, invalid_signature)
        assert is_valid is False
    
    @pytest.mark.asyncio
    @patch("app.services.billing_service.select")
    async def test_process_webhook_event(self, mock_select, mock_db_session, mock_webhook_payload):
        """Test processing webhook events."""
        # Arrange
        billing_service = BillingService()
        billing_service.variant_to_plan = {"ls_variant_123456": "pro"}
        
        # Mock organization and subscription queries
        mock_org = MagicMock()
        mock_org.id = "test_org_id"
        
        mock_subscription = MagicMock()
        mock_subscription.id = "test_subscription_id"
        
        # Update mock_execute to return our mocks
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(side_effect=[mock_org, mock_subscription])
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        result = await billing_service.process_webhook_event(
            event_type="subscription_created",
            payload=mock_webhook_payload,
            db=mock_db_session
        )
        
        # Assert
        assert result["success"] is True
        assert result["action"] == "subscription_created"
        assert result["organization_id"] == "test_org_id"
        assert result["plan"] == "pro"
        mock_db_session.commit.assert_called_once()


class TestCheckoutService:
    """Tests for the checkout service."""
    
    @pytest.mark.asyncio
    @patch("app.services.checkout_service.select")
    async def test_create_checkout_session(self, mock_select, mock_db_session):
        """Test creating a checkout session."""
        # Arrange
        mock_billing_service = MagicMock()
        mock_billing_service.plan_to_variant = {"pro": "ls_variant_123456"}
        mock_billing_service.create_checkout = AsyncMock(return_value={
            "checkout_id": "ls_checkout_123456",
            "checkout_url": "https://checkout.lemonsqueezy.com/123456",
            "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat()
        })
        
        checkout_service = CheckoutService(mock_billing_service)
        
        # Mock organization query
        mock_org = MagicMock()
        mock_org.id = "test_org_id"
        
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_org)
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        checkout = await checkout_service.create_checkout_session(
            data=MagicMock(
                organization_id="test_org_id",
                plan_id="pro"
            ),
            user_id="test_user_id",
            user_email="test@example.com",
            db=mock_db_session
        )
        
        # Assert
        assert checkout["checkout_id"] == "ls_checkout_123456"
        assert checkout["checkout_url"] == "https://checkout.lemonsqueezy.com/123456"
        mock_billing_service.create_checkout.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.checkout_service.select")
    async def test_get_subscription(self, mock_select, mock_db_session, mock_subscription, mock_plan):
        """Test getting subscription details."""
        # Arrange
        checkout_service = CheckoutService(MagicMock())
        
        # Mock subscription and plan queries
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(side_effect=[mock_subscription, mock_plan])
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        subscription = await checkout_service.get_subscription("test_org_id", mock_db_session)
        
        # Assert
        assert subscription["id"] == mock_subscription.id
        assert subscription["organization_id"] == mock_subscription.organization_id
        assert subscription["plan_id"] == mock_subscription.plan_id
        assert subscription["status"] == mock_subscription.status
    
    @pytest.mark.asyncio
    @patch("app.services.checkout_service.select")
    async def test_cancel_subscription(self, mock_select, mock_db_session, mock_subscription, mock_organization):
        """Test cancelling a subscription."""
        # Arrange
        mock_billing_service = MagicMock()
        mock_billing_service.cancel_subscription = AsyncMock(return_value={
            "data": {
                "id": "ls_sub_123456",
                "attributes": {
                    "status": "cancelled"
                }
            }
        })
        
        checkout_service = CheckoutService(mock_billing_service)
        checkout_service.get_subscription = AsyncMock(return_value={
            "id": "test_subscription_id",
            "organization_id": "test_org_id",
            "plan_id": "pro",
            "status": "cancelled"
        })
        
        # Mock subscription and organization queries
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(side_effect=[mock_subscription, mock_organization])
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        result = await checkout_service.cancel_subscription("test_org_id", mock_db_session)
        
        # Assert
        assert result["status"] == "cancelled"
        mock_billing_service.cancel_subscription.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestUsageService:
    """Tests for the usage service."""
    
    @pytest.mark.asyncio
    @patch("app.services.usage_service.select")
    async def test_get_organization_usage(self, mock_select, mock_db_session, mock_organization):
        """Test getting organization usage metrics."""
        # Arrange
        usage_service = UsageService()
        usage_service.plan_limits = {
            "free": {"max_bots": 1, "max_messages_per_month": 100},
            "pro": {"max_bots": 5, "max_messages_per_month": 1000}
        }
        
        # Mock organization query
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_organization)
            result.scalar_one = MagicMock(return_value=3)  # Bot count and knowledge source count
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        usage = await usage_service.get_organization_usage("test_org_id", mock_db_session)
        
        # Assert
        assert usage["plan"] == "pro"
        assert "messages" in usage
        assert "storage" in usage
        assert "bots" in usage
        assert "knowledge_sources" in usage
    
    @pytest.mark.asyncio
    @patch("app.services.usage_service.select")
    async def test_increment_usage(self, mock_select, mock_db_session, mock_organization):
        """Test incrementing usage counter."""
        # Arrange
        usage_service = UsageService()
        usage_service.plan_limits = {
            "free": {"max_bots": 1, "max_messages_per_month": 100},
            "pro": {"max_bots": 5, "max_messages_per_month": 1000}
        }
        
        # Mock organization and usage counter queries
        mock_counter = MagicMock()
        mock_counter.count = 50
        
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(side_effect=[mock_organization, mock_counter])
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        result = await usage_service.increment_usage(
            organization_id="test_org_id",
            metric_type="messages",
            amount=1,
            db=mock_db_session
        )
        
        # Assert
        assert result is True
        assert mock_counter.count == 51
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.usage_service.select")
    async def test_check_limit(self, mock_select, mock_db_session, mock_organization):
        """Test checking resource limit."""
        # Arrange
        usage_service = UsageService()
        usage_service.plan_limits = {
            "free": {"max_bots": 1},
            "pro": {"max_bots": 5}
        }
        
        # Mock organization query
        async def mock_execute(query):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_organization)
            result.scalar_one = MagicMock(return_value=3)  # Bot count
            return result
        
        mock_db_session.execute = mock_execute
        
        # Act
        limit_reached, current_count, limit = await usage_service.check_limit(
            organization_id="test_org_id",
            limit_type="bots",
            db=mock_db_session
        )
        
        # Assert
        assert limit_reached is False
        assert current_count == 3
        assert limit == 5


@pytest.mark.parametrize(
    "endpoint,method,data,expected_status",
    [
        ("/api/v1/billing/checkout", "post", {"plan_id": "pro", "organization_id": "test_org_id"}, 200),
        ("/api/v1/billing/subscriptions/test_org_id", "get", None, 200),
        ("/api/v1/billing/cancel-subscription/test_org_id", "post", None, 200),
        ("/api/v1/billing/plans", "get", None, 200),
        ("/api/v1/billing/usage/test_org_id", "get", None, 200),
    ]
)
@patch("app.core.dependencies.get_current_user")
@patch("app.core.dependencies.require_permission")
@patch("app.api.v1.routes.billing.get_checkout_service")
@patch("app.api.v1.routes.billing.get_usage_service")
@patch("app.core.dependencies.get_db")
def test_billing_endpoints(
    mock_get_db, mock_get_usage_service, mock_get_checkout_service,
    mock_require_permission, mock_get_current_user, endpoint, method,
    data, expected_status, client, mock_db_session, mock_auth_headers
):
    """Test billing endpoints."""
    # Arrange
    mock_get_db.return_value = mock_db_session
    mock_get_current_user.return_value = {"id": "test_user_id", "email": "test@example.com"}
    mock_require_permission.return_value = None
    
    # Mock checkout service
    checkout_service = MagicMock()
    checkout_service.create_checkout_session = AsyncMock(return_value={
        "checkout_id": "ls_checkout_123456",
        "checkout_url": "https://checkout.lemonsqueezy.com/123456"
    })
    checkout_service.get_subscription = AsyncMock(return_value={
        "id": "test_subscription_id",
        "organization_id": "test_org_id",
        "plan_id": "pro",
        "status": "active"
    })
    checkout_service.cancel_subscription = AsyncMock(return_value={
        "id": "test_subscription_id",
        "organization_id": "test_org_id",
        "plan_id": "pro",
        "status": "cancelled"
    })
    checkout_service.list_plans = AsyncMock(return_value=[
        {
            "id": "free",
            "name": "Free",
            "price": 0.0
        },
        {
            "id": "pro",
            "name": "Pro",
            "price": 29.0
        }
    ])
    mock_get_checkout_service.return_value = checkout_service
    
    # Mock usage service
    usage_service = MagicMock()
    usage_service.get_organization_usage = AsyncMock(return_value={
        "plan": "pro",
        "messages": {"used": 450, "limit": 1000},
        "storage": {"used": 2.5, "limit": 10},
        "bots": {"used": 3, "limit": 5}
    })
    mock_get_usage_service.return_value = usage_service
    
    # Act
    if method == "get":
        response = client.get(endpoint, headers=mock_auth_headers)
    elif method == "post":
        response = client.post(endpoint, json=data, headers=mock_auth_headers)
    
    # Assert
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "event_type,expected_success",
    [
        ("subscription_created", True),
        ("subscription_updated", True),
        ("subscription_cancelled", True),
        ("subscription_resumed", True),
        ("subscription_expired", True),
        ("order_created", True),
        ("order_refunded", True),
        ("unknown_event", True),  # Should be handled gracefully
    ]
)
@patch("app.api.v1.routes.billing.get_billing_service")
@patch("app.core.dependencies.get_db")
async def test_webhook_endpoint(
    mock_get_db, mock_get_billing_service, event_type,
    expected_success, client, mock_db_session, mock_webhook_payload
):
    """Test webhook endpoint."""
    # Arrange
    mock_get_db.return_value = mock_db_session
    
    # Update webhook payload with the event type
    mock_webhook_payload["meta"]["event_name"] = event_type
    
    # Mock billing service
    billing_service = MagicMock()
    billing_service.verify_webhook_signature = MagicMock(return_value=True)
    billing_service.process_webhook_event = MagicMock(return_value={
        "success": expected_success,
        "action": event_type
    })
    mock_get_billing_service.return_value = billing_service
    
    # Act
    response = client.post(
        "/api/v1/billing/webhooks/lemonsqueezy",
        json=mock_webhook_payload,
        headers={"x-signature": "test_signature"}
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["event"] == event_type
    billing_service.verify_webhook_signature.assert_called_once()
    billing_service.process_webhook_event.assert_called_once()


@pytest.mark.asyncio
async def test_usage_limiter_middleware():
    """Test usage limiter middleware."""
    # Arrange
    from app.core.middlewares.usage_limiter import UsageLimiterMiddleware
    
    usage_service = MagicMock()
    usage_service.check_limit = AsyncMock(return_value=(False, 3, 5))
    usage_service.increment_usage = AsyncMock(return_value=True)
    
    middleware = UsageLimiterMiddleware()
    middleware.usage_service = usage_service
    
    mock_request = MagicMock()
    mock_db = MagicMock()
    
    # Mock get_current_organization_id
    with patch("app.core.dependencies.get_current_organization_id", AsyncMock(return_value="test_org_id")):
        # Act - Check limit
        await middleware.check_limit(mock_request, "bots", mock_db)
        
        # Assert
        usage_service.check_limit.assert_called_once_with("test_org_id", "bots", mock_db)
        
        # Act - Increment usage
        result = await middleware.increment_usage(mock_request, "messages", 1, mock_db)
        
        # Assert
        assert result is True
        usage_service.increment_usage.assert_called_once_with("test_org_id", "messages", 1, mock_db)
        
        # Test limit reached
        usage_service.check_limit = AsyncMock(return_value=(True, 5, 5))
        
        # Act & Assert - Should raise HTTPException
        with pytest.raises(Exception):
            await middleware.check_limit(mock_request, "bots", mock_db)
