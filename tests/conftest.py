"""
Shared pytest fixtures and configuration for all tests.
"""

import sys
import os
import asyncio
from typing import AsyncGenerator, Generator, Any
from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Set test environment before any imports
os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "test"

# Remove problematic env vars that may be set incorrectly in .env
# Let the Settings use defaults for these
for key in ["SUSPICIOUS_PATTERNS", "API_KEYS", "CORS_ORIGINS"]:
    os.environ.pop(key, None)

# Import app components after setting env vars
from app.main import app
from app.core.config import Settings
from app.core.cache_manager import CacheManager


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (slower, external dependencies)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (slowest, full system)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "smoke: Smoke tests for quick validation"
    )
    config.addinivalue_line(
        "markers", "security: Security-related tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance/load tests"
    )


# ============================================================================
# Event Loop Configuration (for async tests)
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Mock Settings Fixtures
# ============================================================================

@pytest.fixture
def mock_settings():
    """Provide mock settings for testing."""
    settings = MagicMock(spec=Settings)
    
    # Basic settings
    settings.APP_NAME = "Social Flood API Test"
    settings.ENVIRONMENT = "test"
    settings.DEBUG = True
    
    # API Keys
    settings.API_KEYS = ["test_key_1", "test_key_2"]
    
    # Redis settings
    settings.REDIS_URL = None
    settings.REDIS_HOST = "localhost"
    settings.REDIS_PORT = 6379
    settings.REDIS_DB = 1  # Use different DB for tests
    settings.REDIS_PASSWORD = None
    
    # Cache settings
    settings.ENABLE_CACHE = True
    settings.CACHE_TTL = 600
    
    # Database settings
    settings.DATABASE_URL = "sqlite:///./test.db"
    
    # Rate limiting
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMIT_REQUESTS = 100
    settings.RATE_LIMIT_PERIOD = 60
    
    # HTTP Client settings
    settings.HTTP_CONNECTION_POOL_SIZE = 10
    settings.HTTP_MAX_KEEPALIVE_CONNECTIONS = 5
    settings.HTTP_CONNECTION_TIMEOUT = 10.0
    settings.HTTP_READ_TIMEOUT = 30.0
    settings.BATCH_PROCESSING_ENABLED = True
    settings.MAX_CONCURRENT_BATCHES = 5
    
    # Proxy settings
    settings.PROXY_ENABLED = False
    settings.PROXY_URL = None
    settings.PROXY_ROTATION_ENABLED = False
    
    return settings


# ============================================================================
# API Test Client Fixtures
# ============================================================================

@pytest.fixture
def test_client():
    """Provide a test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_test_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide async HTTP client for testing FastAPI endpoints."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def api_headers():
    """Provide standard API headers for testing."""
    return {
        "x-api-key": "test_key_1",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


# ============================================================================
# Cache Manager Fixtures
# ============================================================================

@pytest.fixture
async def cache_manager(mock_settings):
    """Provide a cache manager instance for testing."""
    manager = CacheManager(settings=mock_settings)
    
    # Clear cache before test
    await manager.clear()
    
    yield manager
    
    # Cleanup after test
    await manager.clear()
    if manager.redis_client:
        await manager.redis_client.close()


# ============================================================================
# Mock External API Fixtures
# ============================================================================

@pytest.fixture
def mock_gnews_response():
    """Provide a mock Google News API response."""
    return {
        "articles": [
            {
                "title": "Test Article 1",
                "description": "This is a test article",
                "url": "https://example.com/article1",
                "published_date": "2025-10-08T12:00:00Z",
                "publisher": {
                    "name": "Test Publisher",
                    "url": "https://example.com"
                }
            },
            {
                "title": "Test Article 2",
                "description": "Another test article",
                "url": "https://example.com/article2",
                "published_date": "2025-10-08T13:00:00Z",
                "publisher": {
                    "name": "Test Publisher 2",
                    "url": "https://example.com"
                }
            }
        ]
    }


@pytest.fixture
def mock_trends_response():
    """Provide a mock Google Trends response."""
    return {
        "trends": [
            {
                "query": "trending topic 1",
                "traffic": 100000,
                "related_queries": ["related 1", "related 2"]
            },
            {
                "query": "trending topic 2",
                "traffic": 50000,
                "related_queries": ["related 3", "related 4"]
            }
        ]
    }


@pytest.fixture
def mock_youtube_transcript():
    """Provide a mock YouTube transcript response."""
    return [
        {
            "text": "This is the first segment",
            "start": 0.0,
            "duration": 5.0
        },
        {
            "text": "This is the second segment",
            "start": 5.0,
            "duration": 5.0
        },
        {
            "text": "This is the third segment",
            "start": 10.0,
            "duration": 5.0
        }
    ]


# ============================================================================
# Mock HTTP Response Fixtures
# ============================================================================

@pytest.fixture
def mock_http_response():
    """Provide a mock HTTP response."""
    response = MagicMock()
    response.status_code = 200
    response.text = '{"success": true, "data": "test"}'
    response.json.return_value = {"success": True, "data": "test"}
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture
def mock_http_error_response():
    """Provide a mock HTTP error response."""
    response = MagicMock()
    response.status_code = 500
    response.text = '{"error": "Internal Server Error"}'
    response.json.return_value = {"error": "Internal Server Error"}
    response.headers = {"Content-Type": "application/json"}
    return response


# ============================================================================
# Database Fixtures (for future use)
# ============================================================================

@pytest.fixture
async def test_db():
    """Provide a test database session."""
    # TODO: Implement when database models are created
    # from sqlalchemy import create_engine
    # from sqlalchemy.orm import sessionmaker
    # from app.models import Base
    #
    # engine = create_engine("sqlite:///./test.db")
    # Base.metadata.create_all(engine)
    # Session = sessionmaker(bind=engine)
    # session = Session()
    #
    # yield session
    #
    # session.close()
    # Base.metadata.drop_all(engine)
    pass


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_article_data():
    """Provide sample article data for testing."""
    return {
        "title": "Test Article Title",
        "url": "https://example.com/article",
        "description": "This is a test article description",
        "published_date": "2025-10-08T12:00:00Z",
        "content": "Full article content goes here...",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "language": "en"
    }


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "api_key": "test_api_key_123",
        "is_active": True,
        "created_at": "2025-10-08T12:00:00Z"
    }


@pytest.fixture
def sample_search_params():
    """Provide sample search parameters."""
    return {
        "query": "artificial intelligence",
        "limit": 10,
        "language": "en",
        "country": "US",
        "sort": "relevance"
    }


# ============================================================================
# Helper Functions
# ============================================================================

def create_mock_async_context_manager(return_value=None):
    """Create a mock async context manager."""
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = return_value or AsyncMock()
    mock_cm.__aexit__.return_value = None
    return mock_cm


@pytest.fixture
def mock_async_context_manager():
    """Provide a mock async context manager factory."""
    return create_mock_async_context_manager


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Automatically cleanup after each test."""
    yield
    # Cleanup code runs after each test
    # Add any cleanup logic here that should run after every test
