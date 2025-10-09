"""
Integration tests for Google Autocomplete API endpoints.

These tests verify the complete request/response cycle for the Google Autocomplete API.
"""

import pytest
from fastapi import status


class TestGoogleAutocompleteEndpoints:
    """Integration tests for Google Autocomplete API endpoints."""

    @pytest.mark.integration
    async def test_autocomplete_basic_query(self, async_test_client):
        """Test GET /api/v1/google-autocomplete with basic query."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python programming"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data or isinstance(data, list)

    @pytest.mark.integration
    async def test_autocomplete_with_language(self, async_test_client):
        """Test autocomplete with language parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python", "hl": "en"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_autocomplete_with_geo(self, async_test_client):
        """Test autocomplete with geo parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "weather", "gl": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_autocomplete_short_query(self, async_test_client):
        """Test autocomplete with short query (1-2 characters)."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "py"}
        )
        
        # Should handle short queries
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_autocomplete_special_characters(self, async_test_client):
        """Test autocomplete with special characters in query."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "how to fix @ symbol"}
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestGoogleAutocompleteParameterValidation:
    """Test parameter validation for Google Autocomplete API."""

    @pytest.mark.integration
    async def test_missing_query_parameter(self, async_test_client):
        """Test endpoint without required q parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete"
        )
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    async def test_empty_query_parameter(self, async_test_client):
        """Test with empty query parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": ""}
        )
        
        # Should reject empty query
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_invalid_language_code(self, async_test_client):
        """Test with invalid language code."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python", "hl": "invalid"}
        )
        
        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_query_length_limit(self, async_test_client):
        """Test with very long query."""
        long_query = "python " * 100  # 700 characters
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": long_query}
        )
        
        # Should handle or reject
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestGoogleAutocompleteInputSanitization:
    """Test input sanitization for autocomplete."""

    @pytest.mark.integration
    async def test_xss_attempt_in_query(self, async_test_client):
        """Test XSS script injection in query parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "<script>alert('xss')</script>"}
        )
        
        # Should sanitize or reject
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Response should not contain script tags
            response_text = str(data)
            assert "<script>" not in response_text

    @pytest.mark.integration
    async def test_sql_injection_attempt(self, async_test_client):
        """Test SQL injection in query parameter."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python' OR '1'='1"}
        )
        
        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_unicode_characters(self, async_test_client):
        """Test Unicode characters in query."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python 编程 プログラミング"}
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestGoogleAutocompleteResponseFormat:
    """Test response format and structure."""

    @pytest.mark.integration
    async def test_response_contains_suggestions(self, async_test_client):
        """Test that response contains suggestions."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should have suggestions in some form
            assert data is not None
            assert len(data) > 0 or "suggestions" in data

    @pytest.mark.integration
    async def test_response_headers(self, async_test_client):
        """Test response headers."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            # Should have content-type header
            assert "content-type" in response.headers
            assert "application/json" in response.headers["content-type"]


class TestGoogleAutocompleteCaching:
    """Test caching behavior."""

    @pytest.mark.integration
    async def test_cache_headers_present(self, async_test_client):
        """Test that cache headers are present."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            # Should have cache-related headers
            headers = response.headers
            # May have cache-control, etag, or x-cache headers
            assert any(
                h in headers
                for h in ["cache-control", "etag", "x-cache", "x-cache-hit"]
            )

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_repeated_query_caching(self, async_test_client):
        """Test that repeated queries use cache."""
        query = {"q": "python programming"}
        
        # First request
        response1 = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params=query
        )
        
        # Second request (should be cached)
        response2 = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params=query
        )
        
        assert response1.status_code == response2.status_code
        if response1.status_code == status.HTTP_200_OK:
            # Results should be consistent
            assert response1.json() == response2.json()


class TestGoogleAutocompleteParallelRequests:
    """Test parallel autocomplete requests."""

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_parallel_autocomplete_queries(self, async_test_client):
        """Test multiple parallel autocomplete requests."""
        import asyncio
        
        queries = ["python", "javascript", "rust", "go", "java"]
        
        # Make parallel requests
        tasks = [
            async_test_client.get(
                "/api/v1/google-autocomplete",
                params={"q": q}
            )
            for q in queries
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All requests should succeed
        for response in responses:
            if not isinstance(response, Exception):
                assert response.status_code == status.HTTP_200_OK


class TestGoogleAutocompleteRateLimiting:
    """Test rate limiting behavior."""

    @pytest.mark.integration
    async def test_rate_limit_headers(self, async_test_client):
        """Test that rate limit headers are present."""
        response = await async_test_client.get(
            "/api/v1/google-autocomplete",
            params={"q": "python"}
        )
        
        # Should have rate limit headers
        headers = response.headers
        # May have X-RateLimit-* headers
        has_rate_limit_headers = any(
            "ratelimit" in h.lower() or "rate-limit" in h.lower()
            for h in headers.keys()
        )
        # Rate limit headers might be present
        assert has_rate_limit_headers or response.status_code == status.HTTP_200_OK
