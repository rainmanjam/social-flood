"""
Comprehensive tests for Google Autocomplete API endpoints.

This module provides extensive test coverage for the Google Autocomplete API,
including parameter validation, response parsing, caching, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.google_autocomplete.google_autocomplete_api import (
    router,
    OutputFormat,
    ClientType,
    DataSource,
    generate_cache_key,
    get_cached_or_fetch,
)


class TestGoogleAutocompleteAPI:
    """Test class for Google Autocomplete API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the Google Autocomplete router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/google-autocomplete")
        return TestClient(app)

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client for testing."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '["python", ["python tutorial", "python download", "python for beginners"], [], [], {}]'
        mock_response.json.return_value = [
            "python",
            ["python tutorial", "python download", "python for beginners"],
            [],
            [],
            {"google:clientdata": {"bpc": True, "tlw": False}}
        ]
        mock_client.get.return_value = mock_response
        return mock_client

    # Test utility functions
    def test_generate_cache_key(self):
        """Test cache key generation."""
        key = generate_cache_key("test_endpoint", q="python", output="chrome", gl="US")

        assert "autocomplete:test_endpoint:" in key
        assert "q:python" in key
        assert "output:chrome" in key
        assert "gl:US" in key

    def test_generate_cache_key_with_none_values(self):
        """Test cache key generation with None values."""
        key = generate_cache_key("test_endpoint", q="python", output="chrome", client=None, ds=None)

        assert "autocomplete:test_endpoint:" in key
        assert "q:python" in key
        assert "output:chrome" in key
        assert "client:None" not in key  # None values should be excluded
        assert "ds:None" not in key

    @pytest.mark.asyncio
    @patch('app.api.google_autocomplete.google_autocomplete_api.cache_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_settings')
    async def test_get_cached_or_fetch_cache_hit(self, mock_settings, mock_cache_manager):
        """Test cached data retrieval."""
        mock_settings.return_value.ENABLE_CACHE = True
        mock_cache_manager.get = AsyncMock(return_value={"cached": "data"})

        async def dummy_fetch():
            return {"fresh": "data"}

        result = await get_cached_or_fetch("test_key", dummy_fetch)
        assert result == {"cached": "data"}
        mock_cache_manager.get.assert_called_once_with("test_key", namespace="autocomplete")

    @pytest.mark.asyncio
    @patch('app.api.google_autocomplete.google_autocomplete_api.cache_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_settings')
    async def test_get_cached_or_fetch_cache_miss(self, mock_settings, mock_cache_manager):
        """Test cache miss and data fetching."""
        mock_settings.return_value.ENABLE_CACHE = True
        mock_cache_manager.get = AsyncMock(return_value=None)
        mock_cache_manager.set = AsyncMock()

        async def dummy_fetch():
            return {"fresh": "data"}

        result = await get_cached_or_fetch("test_key", dummy_fetch)
        assert result == {"fresh": "data"}
        mock_cache_manager.set.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_settings')
    async def test_get_cached_or_fetch_cache_disabled(self, mock_settings):
        """Test fetch when caching is disabled."""
        mock_settings.return_value.ENABLE_CACHE = False

        async def dummy_fetch():
            return {"fresh": "data"}

        result = await get_cached_or_fetch("test_key", dummy_fetch)
        assert result == {"fresh": "data"}

    # Test enum values
    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.TOOLBAR.value == "toolbar"
        assert OutputFormat.CHROME.value == "chrome"
        assert OutputFormat.FIREFOX.value == "firefox"
        assert OutputFormat.XML.value == "xml"
        assert OutputFormat.SAFARI.value == "safari"
        assert OutputFormat.OPERA.value == "opera"

    def test_client_type_enum(self):
        """Test ClientType enum values."""
        assert ClientType.FIREFOX.value == "firefox"
        assert ClientType.CHROME.value == "chrome"
        assert ClientType.SAFARI.value == "safari"
        assert ClientType.OPERA.value == "opera"

    def test_data_source_enum(self):
        """Test DataSource enum values."""
        assert DataSource.WEB.value == ""
        assert DataSource.YOUTUBE.value == "yt"
        assert DataSource.IMAGES.value == "i"
        assert DataSource.NEWS.value == "n"
        assert DataSource.SHOPPING.value == "s"
        assert DataSource.VIDEOS.value == "v"
        assert DataSource.BOOKS.value == "b"
        assert DataSource.PATENTS.value == "p"
        assert DataSource.FINANCE.value == "fin"
        assert DataSource.RECIPES.value == "recipe"
        assert DataSource.SCHOLAR.value == "scholar"
        assert DataSource.PLAY.value == "play"
        assert DataSource.MAPS.value == "maps"
        assert DataSource.FLIGHTS.value == "flights"
        assert DataSource.HOTELS.value == "hotels"

    # Test /autocomplete endpoint
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_basic_success(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test basic autocomplete request."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get("/api/v1/google-autocomplete/autocomplete?q=python")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data or "raw_response" in data

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_with_all_parameters(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with all parameters."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={
                "q": "python",
                "output": "chrome",
                "client": "chrome",
                "gl": "US",
                "hl": "en",
                "ds": "yt",
                "spell": 1,
                "cp": 6,
                "psi": 1
            }
        )

        assert response.status_code == 200

    def test_autocomplete_missing_query(self, client):
        """Test autocomplete without query parameter."""
        response = client.get("/api/v1/google-autocomplete/autocomplete")
        assert response.status_code == 422  # Validation error

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_json_format(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with JSON format."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "output": "chrome"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "response_type" in data or "suggestions" in data

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_xml_format(self, mock_sanitizer, mock_proxy, mock_http_manager, client):
        """Test autocomplete with XML format."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup mock HTTP client with XML response
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0"?>
<toplevel>
    <CompleteSuggestion>
        <suggestion data="python tutorial"/>
    </CompleteSuggestion>
    <CompleteSuggestion>
        <suggestion data="python download"/>
    </CompleteSuggestion>
</toplevel>'''
        mock_response.content = mock_response.text.encode()
        mock_http_client.get.return_value = mock_response

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "output": "toolbar"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_with_variations(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with variations mode."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        # Setup settings mock
        with patch('app.api.google_autocomplete.google_autocomplete_api.get_settings') as mock_settings:
            mock_settings.return_value.AUTOCOMPLETE_MAX_PARALLEL_REQUESTS = 5

            response = client.get(
                "/api/v1/google-autocomplete/autocomplete",
                params={"q": "python", "variations": True}
            )

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "keyword_data" in data

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_different_data_sources(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with different data sources."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        # Test each data source
        data_sources = ["yt", "i", "n", "s", "v", "b", "p", "fin", "recipe", "scholar", "play", "maps", "flights", "hotels"]

        for ds in data_sources:
            response = client.get(
                "/api/v1/google-autocomplete/autocomplete",
                params={"q": "python", "ds": ds}
            )
            assert response.status_code == 200

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_different_languages(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with different languages."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        languages = ["en", "es", "fr", "de", "ja"]

        for hl in languages:
            response = client.get(
                "/api/v1/google-autocomplete/autocomplete",
                params={"q": "python", "hl": hl}
            )
            assert response.status_code == 200

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_different_regions(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with different regions."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        regions = ["US", "UK", "CA", "AU", "IN"]

        for gl in regions:
            response = client.get(
                "/api/v1/google-autocomplete/autocomplete",
                params={"q": "python", "gl": gl}
            )
            assert response.status_code == 200

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_with_proxy(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with proxy configuration."""
        mock_proxy.return_value = "http://proxy.example.com:8080"
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python"}
        )

        assert response.status_code == 200

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_http_error(self, mock_sanitizer, mock_proxy, mock_http_manager, client):
        """Test autocomplete with HTTP error."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup mock HTTP client with error response
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_http_client.get.return_value = mock_response

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python"}
        )

        assert response.status_code == 500

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_with_sanitization(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete with input sanitization."""
        mock_proxy.return_value = None

        # Setup sanitizer
        sanitizer_instance = MagicMock()
        sanitizer_instance.settings.INPUT_SANITIZATION_ENABLED = True
        sanitizer_instance.validate_all_params.return_value = {
            "valid": True,
            "errors": [],
            "results": {
                "query": {"sanitized": "python", "valid": True},
                "country_code": {"sanitized": "US", "valid": True},
                "language_code": {"sanitized": "en", "valid": True}
            }
        }
        mock_sanitizer.return_value = sanitizer_instance

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python"}
        )

        assert response.status_code == 200
        sanitizer_instance.validate_all_params.assert_called_once()

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_jsonp_format(self, mock_sanitizer, mock_proxy, mock_http_manager, client):
        """Test autocomplete with JSONP format."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup mock HTTP client with JSONP response
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'myCallback(["python", ["python tutorial", "python download"], [], [], {}])'
        mock_http_client.get.return_value = mock_response

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "callback": "myCallback"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "callback" in data or "suggestions" in data

    def test_autocomplete_parameter_validation(self, client):
        """Test parameter validation."""
        # Test with invalid output format
        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "output": "invalid"}
        )
        assert response.status_code == 422  # Validation error

        # Test with invalid client type
        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "client": "invalid"}
        )
        assert response.status_code == 422  # Validation error

        # Test with invalid data source
        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "ds": "invalid"}
        )
        assert response.status_code == 422  # Validation error

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_empty_response(self, mock_sanitizer, mock_proxy, mock_http_manager, client):
        """Test autocomplete with empty response."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup mock HTTP client with empty response
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '["python", [], [], [], {}]'
        mock_response.json.return_value = ["python", [], [], [], {}]
        mock_http_client.get.return_value = mock_response

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python"}
        )

        assert response.status_code == 200
        data = response.json()
        if "suggestions" in data:
            assert data["suggestions"] == []

    @patch('app.api.google_autocomplete.google_autocomplete_api.get_http_client_manager')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_proxy')
    @patch('app.api.google_autocomplete.google_autocomplete_api.get_input_sanitizer')
    def test_autocomplete_with_metadata(self, mock_sanitizer, mock_proxy, mock_http_manager, client, mock_http_client):
        """Test autocomplete response includes metadata."""
        mock_proxy.return_value = None
        mock_sanitizer.return_value.settings.INPUT_SANITIZATION_ENABLED = False

        # Setup HTTP client manager
        mock_manager = MagicMock()
        mock_manager.get_client.return_value.__aenter__.return_value = mock_http_client
        mock_manager.get_request_count.return_value = 1
        mock_manager.get_connection_stats.return_value = {}
        mock_http_manager.return_value = mock_manager

        response = client.get(
            "/api/v1/google-autocomplete/autocomplete",
            params={"q": "python", "output": "chrome"}
        )

        assert response.status_code == 200
        data = response.json()
        if "metadata" in data:
            assert isinstance(data["metadata"], dict)
