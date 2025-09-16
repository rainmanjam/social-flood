import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestMainApplication:
    """Test the main FastAPI application setup and functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock application settings."""
        settings = MagicMock()
        settings.PROJECT_NAME = "Social Flood"
        settings.DESCRIPTION = "API for social media data aggregation and analysis"
        settings.VERSION = "1.2.0"
        settings.DEBUG = False  # Ensure debug is False for tests
        settings.ENVIRONMENT = "development"
        settings.RATE_LIMIT_ENABLED = True
        settings.RATE_LIMIT_REQUESTS = 100
        settings.RATE_LIMIT_TIMEFRAME = 60
        settings.ENABLE_CACHE = True
        settings.CACHE_TTL = 300
        settings.CORS_ORIGINS = ["*"]
        settings.CORS_METHODS = ["*"]
        settings.CORS_HEADERS = ["*"]
        settings.HOST = "0.0.0.0"
        settings.PORT = 8000
        return settings

    def test_create_application_basic(self, mock_settings):
        """Test basic application creation."""
        with patch('main.settings', mock_settings), \
             patch('main.configure_exception_handlers') as mock_configure_handlers, \
             patch('main.setup_middleware') as mock_setup_middleware, \
             patch('main.limiter', None), \
             patch('main.RATE_LIMITING_AVAILABLE', False), \
             patch('main.METRICS_AVAILABLE', False):

            from main import create_application
            app = create_application()

            assert isinstance(app, FastAPI)
            assert app.title == "Social Flood"
            assert app.description == "API for social media data aggregation and analysis"
            assert app.version == "1.2.0"
            assert app.debug is False

            # Verify middleware and exception handlers were called
            mock_setup_middleware.assert_called_once()
            mock_configure_handlers.assert_called_once_with(app)

    def test_create_application_with_rate_limiting(self, mock_settings):
        """Test application creation with rate limiting enabled."""
        with patch('main.settings', mock_settings), \
             patch('main.configure_exception_handlers'), \
             patch('main.setup_middleware'), \
             patch('main.limiter'), \
             patch('main.RATE_LIMITING_AVAILABLE', True), \
             patch('main.METRICS_AVAILABLE', False), \
             patch('main.RateLimitExceeded', create=True):

            from main import create_application
            app = create_application()

            # Verify rate limiter was set
            assert hasattr(app.state, 'limiter')

    def test_create_application_with_metrics(self, mock_settings):
        """Test application creation with metrics enabled."""
        pytest.importorskip("prometheus_fastapi_instrumentator")

        mock_instrumentator = MagicMock()
        mock_instrumented_app = MagicMock()
        mock_instrumentator.instrument.return_value = mock_instrumented_app

        with patch('main.settings', mock_settings), \
             patch('main.configure_exception_handlers'), \
             patch('main.setup_middleware'), \
             patch('main.limiter', None), \
             patch('main.RATE_LIMITING_AVAILABLE', False), \
             patch('main.METRICS_AVAILABLE', True), \
             patch('prometheus_fastapi_instrumentator.Instrumentator', return_value=mock_instrumentator):

            from main import create_application
            app = create_application()

            # Verify expose was called on the instrumented app
            mock_instrumented_app.expose.assert_called_once_with(app, endpoint="/metrics", include_in_schema=False)

    @pytest.mark.asyncio
    @patch('main.setup_nltk', new_callable=AsyncMock)
    @patch('main.settings')
    async def test_startup_event(self, mock_settings_patch, mock_setup_nltk, mock_settings):
        """Test startup event functionality."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()

        # Manually trigger startup event
        for event_handler in app.router.on_startup:
            await event_handler()

        # Verify NLTK setup was called
        mock_setup_nltk.assert_called_once()

    @patch('main.settings')
    def test_health_check_endpoints(self, mock_settings_patch, mock_settings):
        """Test health check endpoints."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()
        client = TestClient(app)

        # Test basic health check
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.2.0"
        assert data["environment"] == "development"
        assert "timestamp" in data

        # Test ping endpoint
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"ping": "pong"}

        # Test status endpoint
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["version"] == "1.2.0"
        assert data["environment"] == "development"
        assert "timestamp" in data
        assert "uptime" in data

    @pytest.mark.asyncio
    @patch('main.check_health', new_callable=AsyncMock)
    @patch('main.settings')
    def test_detailed_health_check(self, mock_settings_patch, mock_check_health, mock_settings):
        """Test detailed health check endpoint."""
        mock_check_health.return_value = {"status": "healthy", "details": {}}
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()
        client = TestClient(app)

        response = client.get("/health/detailed")
        assert response.status_code == 200

        # Verify check_health was called with correct parameters
        mock_check_health.assert_called_once()
        call_args = mock_check_health.call_args
        assert call_args[1]["include_details"] is True

    @patch('main.settings')
    def test_api_config_endpoint(self, mock_settings_patch, mock_settings):
        """Test API configuration endpoint."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT
        mock_settings_patch.RATE_LIMIT_ENABLED = mock_settings.RATE_LIMIT_ENABLED
        mock_settings_patch.RATE_LIMIT_REQUESTS = mock_settings.RATE_LIMIT_REQUESTS
        mock_settings_patch.RATE_LIMIT_TIMEFRAME = mock_settings.RATE_LIMIT_TIMEFRAME
        mock_settings_patch.ENABLE_CACHE = mock_settings.ENABLE_CACHE
        mock_settings_patch.CACHE_TTL = mock_settings.CACHE_TTL
        mock_settings_patch.CORS_ORIGINS = mock_settings.CORS_ORIGINS
        mock_settings_patch.CORS_METHODS = mock_settings.CORS_METHODS
        mock_settings_patch.CORS_HEADERS = mock_settings.CORS_HEADERS

        from main import create_application
        app = create_application()
        client = TestClient(app)

        response = client.get("/api-config")
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Social Flood"
        assert data["version"] == "1.2.0"
        assert data["environment"] == "development"
        assert "rate_limiting" in data
        assert "caching" in data
        assert "cors" in data

    @patch('main.settings')
    def test_config_sources_endpoint(self, mock_settings_patch, mock_settings):
        """Test configuration sources endpoint."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()
        client = TestClient(app)

        response = client.get("/config-sources")
        assert response.status_code == 200
        data = response.json()

        assert "environment_variables" in data
        assert "env_file" in data
        assert "defaults" in data

    @patch('main.settings')
    def test_custom_docs_endpoints(self, mock_settings_patch, mock_settings):
        """Test custom documentation endpoints."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()
        client = TestClient(app)

        # Test custom swagger docs
        response = client.get("/api/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

        # Test custom redoc
        response = client.get("/api/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()

    @patch('main.settings')
    def test_router_inclusion(self, mock_settings_patch, mock_settings):
        """Test that API routers are properly included."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()

        # Check that routers are included by verifying routes exist
        routes = [route.path for route in app.routes]
        # Look for routes that contain the API paths
        api_routes = [route for route in routes if route.startswith("/api/v1")]
        assert len(api_routes) > 0, f"No API routes found. Available routes: {routes}"

    @patch('main.settings')
    def test_app_state_initialization(self, mock_settings_patch, mock_settings):
        """Test that app state is properly initialized."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        from main import create_application
        app = create_application()

        # Check that start_time is set
        assert hasattr(app.state, 'start_time')
        assert isinstance(app.state.start_time, float)

    @patch('main.settings')
    def test_direct_execution(self, mock_settings_patch, mock_settings):
        """Test that the main module can be imported and has expected attributes."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT

        # Test that we can import the main module
        import main

        # Verify that the main module has the expected attributes
        assert hasattr(main, 'create_application')
        assert hasattr(main, 'app')

        # Verify that create_application is callable
        assert callable(main.create_application)

    @patch('main.settings')
    def test_openapi_schema_generation(self, mock_settings_patch, mock_settings):
        """Test OpenAPI schema generation."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT
        mock_settings_patch.DESCRIPTION = mock_settings.DESCRIPTION  # Add missing description

        from main import create_application
        app = create_application()

        # Test that OpenAPI schema can be generated
        schema = app.openapi()
        assert "info" in schema
        assert schema["info"]["title"] == "Social Flood"
        assert schema["info"]["version"] == "1.2.0"

    @patch('main.settings')
    def test_cors_configuration(self, mock_settings_patch, mock_settings):
        """Test CORS configuration in API config."""
        # Configure the mock settings with the fixture values
        mock_settings_patch.PROJECT_NAME = mock_settings.PROJECT_NAME
        mock_settings_patch.VERSION = mock_settings.VERSION
        mock_settings_patch.ENVIRONMENT = mock_settings.ENVIRONMENT
        mock_settings_patch.RATE_LIMIT_ENABLED = mock_settings.RATE_LIMIT_ENABLED
        mock_settings_patch.RATE_LIMIT_REQUESTS = mock_settings.RATE_LIMIT_REQUESTS
        mock_settings_patch.RATE_LIMIT_TIMEFRAME = mock_settings.RATE_LIMIT_TIMEFRAME
        mock_settings_patch.ENABLE_CACHE = mock_settings.ENABLE_CACHE
        mock_settings_patch.CACHE_TTL = mock_settings.CACHE_TTL
        mock_settings_patch.CORS_ORIGINS = mock_settings.CORS_ORIGINS
        mock_settings_patch.CORS_METHODS = mock_settings.CORS_METHODS
        mock_settings_patch.CORS_HEADERS = mock_settings.CORS_HEADERS

        from main import create_application
        app = create_application()
        client = TestClient(app)

        response = client.get("/api-config")
        assert response.status_code == 200
        data = response.json()

        cors_config = data["cors"]
        assert cors_config["origins"] == ["*"]
        assert cors_config["methods"] == ["*"]
        assert cors_config["headers"] == ["*"]
