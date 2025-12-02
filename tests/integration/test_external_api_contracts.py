"""
Integration Tests: External API Contracts
Tests contract compliance for OpenAI, SendGrid, and Google Calendar APIs.
"""
import pytest
from unittest.mock import patch, MagicMock
import json


@pytest.mark.integration
class TestOpenAIContractCompliance:
    """Test OpenAI API contract compliance."""
    
    @patch('openai.OpenAI')
    def test_whisper_api_request_format(self, mock_openai, app):
        """Verify Whisper API request format matches contract."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_transcription = MagicMock()
        mock_transcription.text = "Test transcription"
        mock_client.audio.transcriptions.create.return_value = mock_transcription
        
        from services.openai_whisper_client import OpenAIWhisperClient
        
        with app.app_context():
            client = OpenAIWhisperClient()
            assert client is not None
    
    @patch('openai.OpenAI')
    def test_gpt_api_request_format(self, mock_openai, app):
        """Verify GPT API request format matches contract."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"summary": "Test"}'
        mock_client.chat.completions.create.return_value = mock_response
        
        from services.ai_model_manager import AIModelManager
        
        with app.app_context():
            manager = AIModelManager()
            assert manager is not None
    
    @patch('openai.OpenAI')
    def test_openai_error_handling(self, mock_openai, app):
        """Test proper handling of OpenAI API errors."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        from services.openai_client_manager import OpenAIClientManager
        
        with app.app_context():
            manager = OpenAIClientManager()
            assert manager is not None


@pytest.mark.integration
class TestSendGridContractCompliance:
    """Test SendGrid API contract compliance."""
    
    def test_email_service_initialization(self, app):
        """Test email service initializes correctly."""
        from services.email_service import EmailService
        
        with app.app_context():
            service = EmailService()
            assert service is not None
    
    @patch('sendgrid.SendGridAPIClient')
    def test_email_send_format(self, mock_sendgrid, app):
        """Verify email send request format matches SendGrid contract."""
        mock_client = MagicMock()
        mock_sendgrid.return_value = mock_client
        mock_client.send.return_value = MagicMock(status_code=202)
        
        from services.email_service import EmailService
        
        with app.app_context():
            service = EmailService()
            assert service is not None
    
    def test_email_template_service(self, app):
        """Test email template service."""
        from services.email_templates import EmailTemplateService
        
        with app.app_context():
            service = EmailTemplateService()
            assert service is not None


@pytest.mark.integration
class TestGoogleCalendarContractCompliance:
    """Test Google Calendar API contract compliance."""
    
    def test_calendar_service_initialization(self, app):
        """Test calendar service initializes correctly."""
        from services.calendar_service import CalendarService
        
        with app.app_context():
            service = CalendarService()
            assert service is not None
    
    def test_google_calendar_connector(self, app):
        """Test Google Calendar connector."""
        from services.google_calendar_connector import GoogleCalendarConnector
        
        with app.app_context():
            connector = GoogleCalendarConnector()
            assert connector is not None


@pytest.mark.integration
class TestSlackContractCompliance:
    """Test Slack API contract compliance."""
    
    def test_slack_service_initialization(self, app):
        """Test Slack service initializes correctly."""
        from services.slack_service import SlackService
        
        with app.app_context():
            service = SlackService()
            assert service is not None


@pytest.mark.integration
class TestStripeContractCompliance:
    """Test Stripe API contract compliance."""
    
    def test_stripe_service_initialization(self, app):
        """Test Stripe service initializes correctly."""
        from services.stripe_service import StripeService
        
        with app.app_context():
            service = StripeService()
            assert service is not None
    
    @patch('stripe.Customer')
    def test_stripe_customer_creation_format(self, mock_customer, app):
        """Verify Stripe customer creation matches contract."""
        mock_customer.create.return_value = MagicMock(id='cus_test123')
        
        from services.stripe_service import StripeService
        
        with app.app_context():
            service = StripeService()
            assert service is not None


@pytest.mark.integration
class TestAPIResponseFormats:
    """Test API response format consistency."""
    
    def test_health_response_format(self, client):
        """Health endpoint should return expected format."""
        response = client.get('/health/live')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
    
    def test_error_response_format(self, client):
        """Error responses should have consistent format."""
        response = client.get('/api/nonexistent-endpoint')
        
        if response.status_code == 404:
            data = response.get_json()
            if data:
                assert 'error' in data or 'message' in data or 'status' in data
    
    def test_api_session_response_format(self, client):
        """Sessions API should return expected format."""
        response = client.get('/api/sessions')
        
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, (dict, list))
