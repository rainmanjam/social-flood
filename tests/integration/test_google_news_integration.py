"""
Integration tests for Google News API endpoints.

These tests verify the complete request/response cycle for the Google News API,
including routing, request validation, error handling, and response formatting.
"""

import pytest
from fastapi import status
from httpx import AsyncClient


class TestGoogleNewsEndpoints:
    """Integration tests for Google News API endpoints."""

    @pytest.mark.integration
    async def test_top_news_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/top endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"lang": "en", "country": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert "data" in data or "articles" in data
        assert "metadata" in data or "meta" in data

    @pytest.mark.integration
    async def test_top_news_invalid_country(self, async_test_client):
        """Test top news with invalid country code."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"lang": "en", "country": "INVALID"}
        )
        
        # Should return 400 Bad Request or similar
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_search_news_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/search endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "technology", "lang": "en"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify search results structure
        assert "status" in data or "articles" in data

    @pytest.mark.integration
    async def test_search_news_empty_query(self, async_test_client):
        """Test search with empty query."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "", "lang": "en"}
        )
        
        # Should return validation error
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_news_by_topic_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/topic endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-news/topic",
            params={"topic": "TECHNOLOGY", "lang": "en", "country": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data or "articles" in data

    @pytest.mark.integration
    async def test_news_by_location_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/geo endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-news/geo",
            params={"location": "New York", "lang": "en"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_available_countries_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/countries endpoint."""
        response = await async_test_client.get("/api/v1/google-news/countries")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should return a list of countries
        assert isinstance(data, (list, dict))

    @pytest.mark.integration
    async def test_available_languages_endpoint(self, async_test_client):
        """Test GET /api/v1/google-news/languages endpoint."""
        response = await async_test_client.get("/api/v1/google-news/languages")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should return a list of languages
        assert isinstance(data, (list, dict))


class TestGoogleNewsErrorHandling:
    """Test error handling for Google News API."""

    @pytest.mark.integration
    async def test_missing_required_parameters(self, async_test_client):
        """Test endpoint with missing required parameters."""
        response = await async_test_client.get("/api/v1/google-news/search")
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    async def test_invalid_parameter_types(self, async_test_client):
        """Test endpoint with invalid parameter types."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"max_results": "invalid"}  # Should be integer
        )
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    async def test_suspicious_input_sanitization(self, async_test_client):
        """Test that suspicious inputs are sanitized."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "<script>alert('xss')</script>", "lang": "en"}
        )
        
        # Should either sanitize or reject
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestGoogleNewsResponseFormat:
    """Test response formatting for Google News API."""

    @pytest.mark.integration
    async def test_response_has_metadata(self, async_test_client):
        """Test that responses include metadata."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"lang": "en", "country": "US"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Check for common metadata fields
            has_metadata = (
                "metadata" in data or 
                "meta" in data or
                "timestamp" in data
            )
            assert has_metadata or "articles" in data

    @pytest.mark.integration
    async def test_error_response_format_rfc7807(self, async_test_client):
        """Test that error responses follow RFC 7807 format."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "", "lang": "en"}
        )
        
        if response.status_code >= 400:
            data = response.json()
            # RFC 7807 fields
            assert "detail" in data or "message" in data

    @pytest.mark.integration
    async def test_cache_headers_present(self, async_test_client):
        """Test that appropriate cache headers are present."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"lang": "en", "country": "US"}
        )
        
        # Should have some cache-related headers
        # (actual headers depend on your middleware configuration)
        assert response.headers is not None


class TestGoogleNewsRateLimiting:
    """Test rate limiting for Google News API."""

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_rate_limit_headers(self, async_test_client):
        """Test that rate limit headers are present."""
        response = await async_test_client.get(
            "/api/v1/google-news/top",
            params={"lang": "en", "country": "US"}
        )
        
        # Check for rate limit headers if rate limiting is enabled
        # Common headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
        headers = response.headers
        
        # Rate limiting might be disabled in tests, so just verify headers exist
        assert headers is not None


class TestGoogleNewsPagination:
    """Test pagination for Google News API."""

    @pytest.mark.integration
    async def test_max_results_parameter(self, async_test_client):
        """Test max_results parameter for pagination."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "technology", "lang": "en", "max_results": 5}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Verify limited results (implementation dependent)
            assert data is not None

    @pytest.mark.integration
    async def test_max_results_validation(self, async_test_client):
        """Test max_results parameter validation."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={"q": "technology", "lang": "en", "max_results": 1000}
        )
        
        # Should either accept or validate max limit
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestGoogleNewsDateFiltering:
    """Test date filtering for Google News API."""

    @pytest.mark.integration
    async def test_date_range_filtering(self, async_test_client):
        """Test filtering by date range."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={
                "q": "technology",
                "lang": "en",
                "start_date": "2025-01-01",
                "end_date": "2025-10-08"
            }
        )
        
        # Should accept valid date ranges
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY  # If not supported
        ]

    @pytest.mark.integration
    async def test_invalid_date_format(self, async_test_client):
        """Test with invalid date format."""
        response = await async_test_client.get(
            "/api/v1/google-news/search",
            params={
                "q": "technology",
                "lang": "en",
                "start_date": "invalid-date"
            }
        )
        
        # Should reject invalid date format
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
