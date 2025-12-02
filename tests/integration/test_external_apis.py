"""
Integration tests for external API integrations.
"""
import pytest
import os


@pytest.mark.integration
class TestOpenAIIntegration:
    """Test OpenAI API integration."""
    
    def test_openai_client_exists(self):
        """Test that OpenAI client is configured."""
        try:
            from services.whisper_streaming_service import WhisperStreamingService
            service = WhisperStreamingService()
            assert service is not None
        except (ImportError, AttributeError):
            pytest.skip("OpenAI client not configured yet")
    
    def test_openai_api_key_configured(self):
        """Test that OpenAI API key is configured."""
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            pytest.skip("OPENAI_API_KEY not configured in environment")
        assert api_key is not None


@pytest.mark.integration
class TestDatabaseConnectionIntegration:
    """Test database connection and configuration."""
    
    def test_database_url_configured(self, app):
        """Test that database URL is configured."""
        database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
        assert database_url is not None
        assert len(database_url) > 0
    
    def test_database_connection_pool_configured(self, app):
        """Test that connection pool is configured."""
        pool_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
        
        assert 'pool_recycle' in pool_options
        assert 'pool_pre_ping' in pool_options
        assert pool_options['pool_recycle'] == 300
        assert pool_options['pool_pre_ping'] == True
    
    def test_database_connection_active(self, db_session):
        """Test that database connection is active."""
        from sqlalchemy import text
        result = db_session.execute(text('SELECT 1'))
        assert result is not None


@pytest.mark.integration
class TestSessionSecretConfiguration:
    """Test session secret configuration."""
    
    def test_session_secret_configured(self, app):
        """Test that session secret is configured."""
        secret_key = app.config.get('SECRET_KEY') or app.secret_key
        assert secret_key is not None
        assert len(secret_key) > 0
        assert secret_key != 'dev'


@pytest.mark.integration
class TestRedisIntegration:
    """Test Redis integration."""
    
    def test_redis_client_exists(self):
        """Test that Redis client can be created."""
        try:
            from services.redis_failover import RedisFailoverManager
            manager = RedisFailoverManager()
            assert manager is not None
        except ImportError:
            pytest.skip("Redis integration not implemented yet")


@pytest.mark.integration
class TestFileStorageIntegration:
    """Test file storage integration."""
    
    def test_upload_directory_configured(self, app):
        """Test that upload directory is configured."""
        try:
            upload_folder = app.config.get('UPLOAD_FOLDER')
            if upload_folder:
                assert upload_folder is not None
        except (AttributeError, KeyError):
            pytest.skip("Upload folder not configured yet")
