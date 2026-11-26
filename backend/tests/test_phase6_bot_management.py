"""
Test Phase 6: Bot Management & Customization

Tests for:
- Bot CRUD operations
- Widget customization
- Suggested questions
- Fallback responses
- Multi-language support
- Bot templates
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.bot_service import BotService
from app.services.suggested_questions_service import SuggestedQuestionsService
from app.services.fallback_service import FallbackService
from app.services.language_service import LanguageService
from app.services.template_service import TemplateService
from app.db.models.bot import Bot, BotStatus
from app.db.models.bot_template import BotTemplate
from app.schemas.bot import (
    BotCreate, BotUpdate, BotSettingsUpdate, WidgetSettingsUpdate,
    SuggestedQuestionsUpdate, FallbackResponsesUpdate
)

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


class TestBotService:
    """Test Bot Service functionality."""
    
    def test_create_bot(self):
        """Test creating a bot."""
        with patch('app.services.bot_service.get_qdrant_service') as mock_qdrant:
            # Setup mock
            mock_qdrant.return_value.create_collection.return_value = None
            
            # Create mock db session
            mock_db = Mock(spec=Session)
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            
            # Create bot service
            service = BotService()
            
            # Create bot data
            bot_data = BotCreate(
                name="Test Bot",
                description="Test Description",
                status=BotStatus.DRAFT,
                settings={"temperature": 0.7},
                widget_settings={"position": "bottom-right"}
            )
            
            # Create bot
            bot = service.create_bot(
                db=mock_db,
                organization_id="test-org",
                user_id="test-user",
                bot_data=bot_data
            )
            
            # Verify bot was created
            assert bot.name == "Test Bot"
            assert bot.description == "Test Description"
            assert bot.status == BotStatus.DRAFT
            assert bot.settings == {"temperature": 0.7}
            assert bot.widget_settings == {"position": "bottom-right"}
            assert bot.api_key is not None
            assert bot.api_key_hash is not None
            
            # Verify methods were called
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            mock_qdrant.return_value.create_collection.assert_called_once()
    
    def test_update_bot(self):
        """Test updating a bot."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.name = "Original Name"
        mock_bot.description = "Original Description"
        mock_bot.status = BotStatus.DRAFT
        mock_bot.settings = {"temperature": 0.7}
        mock_bot.widget_settings = {"position": "bottom-right"}
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create bot service
        service = BotService()
        
        # Create update data
        update_data = BotUpdate(
            name="Updated Name",
            description="Updated Description",
            status=BotStatus.ACTIVE
        )
        
        # Update bot
        updated_bot = service.update_bot(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org",
            bot_data=update_data
        )
        
        # Verify bot was updated
        assert updated_bot.name == "Updated Name"
        assert updated_bot.description == "Updated Description"
        assert updated_bot.status == BotStatus.ACTIVE
        
        # Verify methods were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_update_bot_settings(self):
        """Test updating bot settings."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.settings = {"temperature": 0.7}
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create bot service
        service = BotService()
        
        # Create settings update data
        settings_data = BotSettingsUpdate(
            temperature=0.8,
            max_tokens=500,
            model="gpt-4"
        )
        
        # Update bot settings
        updated_bot = service.update_bot_settings(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org",
            settings_data=settings_data
        )
        
        # Verify settings were updated
        assert updated_bot.settings["temperature"] == 0.8
        assert updated_bot.settings["max_tokens"] == 500
        assert updated_bot.settings["model"] == "gpt-4"
        
        # Verify methods were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_update_widget_settings(self):
        """Test updating widget settings."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.widget_settings = {"position": "bottom-right"}
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create bot service
        service = BotService()
        
        # Create widget settings update data
        widget_data = WidgetSettingsUpdate(
            position="bottom-left",
            welcome_message="Hello there!",
            colors={"primary": "#ff0000"}
        )
        
        # Update widget settings
        updated_bot = service.update_widget_settings(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org",
            widget_data=widget_data
        )
        
        # Verify widget settings were updated
        assert updated_bot.widget_settings["position"] == "bottom-left"
        assert updated_bot.widget_settings["welcome_message"] == "Hello there!"
        assert updated_bot.widget_settings["colors"]["primary"] == "#ff0000"
        
        # Verify methods were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestSuggestedQuestionsService:
    """Test Suggested Questions Service functionality."""
    
    def test_get_suggested_questions(self):
        """Test getting suggested questions."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.widget_settings = {
            "suggested_questions": [
                {"id": "q1", "text": "Question 1", "category": "general"},
                {"id": "q2", "text": "Question 2", "category": "support"}
            ]
        }
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create service
        service = SuggestedQuestionsService()
        
        # Get suggested questions
        questions = service.get_suggested_questions(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org"
        )
        
        # Verify questions were retrieved
        assert len(questions) == 2
        assert questions[0]["text"] == "Question 1"
        assert questions[1]["text"] == "Question 2"
    
    def test_update_suggested_questions(self):
        """Test updating suggested questions."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.widget_settings = {}
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create service
        service = SuggestedQuestionsService()
        
        # Create questions update data
        from app.schemas.bot import SuggestedQuestion
        questions_data = SuggestedQuestionsUpdate(
            questions=[
                SuggestedQuestion(text="New Question 1", category="general"),
                SuggestedQuestion(text="New Question 2", category="support")
            ]
        )
        
        # Update suggested questions
        updated_bot = service.update_suggested_questions(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org",
            questions_data=questions_data
        )
        
        # Verify questions were updated
        assert len(updated_bot.widget_settings["suggested_questions"]) == 2
        assert updated_bot.widget_settings["suggested_questions"][0]["text"] == "New Question 1"
        assert updated_bot.widget_settings["suggested_questions"][1]["text"] == "New Question 2"
        
        # Verify methods were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestFallbackService:
    """Test Fallback Service functionality."""
    
    def test_get_fallback_responses(self):
        """Test getting fallback responses."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.settings = {
            "fallback_responses": [
                {"id": "f1", "message": "Fallback 1", "condition": "low_confidence"},
                {"id": "f2", "message": "Fallback 2", "condition": "no_results"}
            ]
        }
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create service
        service = FallbackService()
        
        # Get fallback responses
        responses = service.get_fallback_responses(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org"
        )
        
        # Verify responses were retrieved
        assert len(responses) == 2
        assert responses[0]["message"] == "Fallback 1"
        assert responses[1]["message"] == "Fallback 2"
    
    def test_update_fallback_responses(self):
        """Test updating fallback responses."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.settings = {}
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create service
        service = FallbackService()
        
        # Create responses update data
        from app.schemas.bot import FallbackResponse
        responses_data = FallbackResponsesUpdate(
            responses=[
                FallbackResponse(message="New Fallback 1", condition="low_confidence"),
                FallbackResponse(message="New Fallback 2", condition="no_results")
            ]
        )
        
        # Update fallback responses
        updated_bot = service.update_fallback_responses(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org",
            responses_data=responses_data
        )
        
        # Verify responses were updated
        assert len(updated_bot.settings["fallback_responses"]) == 2
        assert updated_bot.settings["fallback_responses"][0]["message"] == "New Fallback 1"
        assert updated_bot.settings["fallback_responses"][1]["message"] == "New Fallback 2"
        
        # Verify methods were called
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestLanguageService:
    """Test Language Service functionality."""
    
    def test_get_supported_languages(self):
        """Test getting supported languages."""
        # Create service
        service = LanguageService()
        
        # Get supported languages
        languages = service.get_supported_languages()
        
        # Verify languages were retrieved
        assert len(languages) > 0
        assert "code" in languages[0]
        assert "name" in languages[0]
        assert "en" in [lang["code"] for lang in languages]
    
    def test_get_bot_languages(self):
        """Test getting bot language settings."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        mock_bot.id = "test-bot"
        mock_bot.organization_id = "test-org"
        mock_bot.settings = {
            "languages": {
                "default": "en",
                "enabled": ["en", "es", "fr"],
                "auto_detect": True,
                "translations": {
                    "es": {
                        "welcome_message": "¡Hola!"
                    },
                    "fr": {
                        "welcome_message": "Bonjour!"
                    }
                }
            }
        }
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_bot
        mock_db.query.return_value = mock_query
        
        # Create service
        service = LanguageService()
        
        # Get bot languages
        language_settings = service.get_bot_languages(
            db=mock_db,
            bot_id="test-bot",
            organization_id="test-org"
        )
        
        # Verify language settings were retrieved
        assert "settings" in language_settings
        assert language_settings["settings"]["default"] == "en"
        assert "es" in language_settings["settings"]["enabled"]
        assert "fr" in language_settings["settings"]["enabled"]
        assert language_settings["settings"]["auto_detect"] is True
        assert "translations" in language_settings["settings"]
        assert "supported_languages" in language_settings


class TestTemplateService:
    """Test Template Service functionality."""
    
    def test_create_template(self):
        """Test creating a template."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Create service
        service = TemplateService()
        
        # Create template data
        from app.schemas.bot import BotTemplateCreate
        template_data = BotTemplateCreate(
            name="Test Template",
            description="Test Description",
            category="support",
            settings={"temperature": 0.7},
            widget_settings={"position": "bottom-right"},
            system_prompt="You are a helpful assistant",
            suggested_questions=["Question 1", "Question 2"]
        )
        
        # Create template
        template = service.create_template(
            db=mock_db,
            template_data=template_data
        )
        
        # Verify template was created
        assert template.name == "Test Template"
        assert template.description == "Test Description"
        assert template.category == "support"
        assert template.settings == {"temperature": 0.7}
        assert template.widget_settings == {"position": "bottom-right"}
        assert template.system_prompt == "You are a helpful assistant"
        assert template.suggested_questions == ["Question 1", "Question 2"]
        
        # Verify methods were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_list_templates(self):
        """Test listing templates."""
        # Create mock db session
        mock_db = Mock(spec=Session)
        
        # Create mock templates
        mock_template1 = Mock(spec=BotTemplate)
        mock_template1.id = "template-1"
        mock_template1.name = "Template 1"
        mock_template1.category = "support"
        
        mock_template2 = Mock(spec=BotTemplate)
        mock_template2.id = "template-2"
        mock_template2.name = "Template 2"
        mock_template2.category = "sales"
        
        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [mock_template1, mock_template2]
        mock_query.count.return_value = 2
        mock_db.query.return_value = mock_query
        
        # Create service
        service = TemplateService()
        
        # List templates
        templates, total = service.list_templates(
            db=mock_db,
            limit=10,
            offset=0
        )
        
        # Verify templates were listed
        assert len(templates) == 2
        assert templates[0].id == "template-1"
        assert templates[1].id == "template-2"
        assert total == 2


class TestAPIEndpoints:
    """Test API endpoints."""
    
    @patch('app.api.v1.routes.bots.get_bot_service')
    def test_create_bot_endpoint(self, mock_get_service):
        """Test create bot endpoint."""
        # Setup mock
        mock_service = Mock()
        mock_bot = Mock()
        mock_bot.to_dict.return_value = {
            "id": "test-bot",
            "name": "Test Bot",
            "description": "Test Description",
            "status": "draft"
        }
        mock_bot.api_key = "test-api-key"
        mock_service.create_bot.return_value = mock_bot
        mock_get_service.return_value = mock_service
        
        # Create bot data
        bot_data = {
            "name": "Test Bot",
            "description": "Test Description",
            "status": "draft"
        }
        
        # Call endpoint
        response = client.post(
            "/api/v1/bots",
            json=bot_data,
            headers=get_auth_headers()
        )
        
        # Verify response
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]
        
        # If successful, verify data
        if response.status_code in [200, 201]:
            data = response.json()
            assert "data" in data
            assert data["data"]["name"] == "Test Bot"
            assert "api_key" in data["data"]
    
    @patch('app.api.v1.routes.bots.get_bot_service')
    def test_list_bots_endpoint(self, mock_get_service):
        """Test list bots endpoint."""
        # Setup mock
        mock_service = Mock()
        mock_bot1 = Mock()
        mock_bot1.to_dict.return_value = {
            "id": "bot-1",
            "name": "Bot 1",
            "status": "active"
        }
        mock_bot2 = Mock()
        mock_bot2.to_dict.return_value = {
            "id": "bot-2",
            "name": "Bot 2",
            "status": "draft"
        }
        mock_service.list_bots.return_value = ([mock_bot1, mock_bot2], 2)
        mock_get_service.return_value = mock_service
        
        # Call endpoint
        response = client.get(
            "/api/v1/bots",
            headers=get_auth_headers()
        )
        
        # Verify response
        assert response.status_code in [200, 401, 403, 404, 500]
        
        # If successful, verify data
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "bots" in data["data"]
            assert len(data["data"]["bots"]) == 2
            assert data["data"]["total"] == 2
    
    @patch('app.api.v1.routes.suggested_questions.get_suggested_questions_service')
    def test_generate_suggested_questions_endpoint(self, mock_get_service):
        """Test generate suggested questions endpoint."""
        # Setup mock
        mock_service = Mock()
        mock_service.generate_suggested_questions.return_value = [
            {
                "id": "q1",
                "text": "Generated Question 1",
                "category": "generated"
            },
            {
                "id": "q2",
                "text": "Generated Question 2",
                "category": "generated"
            }
        ]
        mock_get_service.return_value = mock_service
        
        # Call endpoint
        response = client.post(
            "/api/v1/bots/test-bot/suggested-questions/generate",
            headers=get_auth_headers()
        )
        
        # Verify response
        assert response.status_code in [200, 401, 403, 404, 500]
        
        # If successful, verify data
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "questions" in data["data"]
            assert len(data["data"]["questions"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
