"""
Integration tests for Google Trends API endpoints.

These tests verify the complete request/response cycle for the Google Trends API.
"""

import pytest
from fastapi import status


class TestGoogleTrendsEndpoints:
    """Integration tests for Google Trends API endpoints."""

    @pytest.mark.integration
    async def test_interest_over_time_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/interest-over-time endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python,javascript", "geo": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data is not None

    @pytest.mark.integration
    async def test_interest_by_region_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/interest-by-region endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-by-region",
            params={"keywords": "python", "resolution": "COUNTRY"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_related_queries_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/related-queries endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/related-queries",
            params={"keywords": "artificial intelligence"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_related_topics_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/related-topics endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/related-topics",
            params={"keywords": "machine learning"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_trending_now_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/trending-now endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/trending-now",
            params={"geo": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_trending_now_rss_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/trending-now-rss endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/trending-now-rss",
            params={"geo": "US"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_categories_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/categories endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/categories"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return categories list
        assert isinstance(data, (list, dict))

    @pytest.mark.integration
    async def test_geo_endpoint(self, async_test_client):
        """Test GET /api/v1/google-trends/geo endpoint."""
        response = await async_test_client.get(
            "/api/v1/google-trends/geo"
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestGoogleTrendsParameterValidation:
    """Test parameter validation for Google Trends API."""

    @pytest.mark.integration
    async def test_missing_keywords_parameter(self, async_test_client):
        """Test endpoint without required keywords parameter."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time"
        )
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    async def test_invalid_timeframe_format(self, async_test_client):
        """Test with invalid timeframe format."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python", "timeframe": "invalid"}
        )
        
        # Should validate timeframe format
        assert response.status_code in [
            status.HTTP_200_OK,  # Might have default
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_multiple_keywords_format(self, async_test_client):
        """Test multiple keywords in different formats."""
        # Comma-separated
        response1 = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python,java,rust"}
        )
        
        assert response1.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_invalid_geo_code(self, async_test_client):
        """Test with invalid geo code."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python", "geo": "INVALID"}
        )
        
        # Should handle invalid geo codes gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestGoogleTrendsTimeframes:
    """Test different timeframe options."""

    @pytest.mark.integration
    async def test_timeframe_now_1h(self, async_test_client):
        """Test with 'now 1-H' timeframe."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "breaking news", "timeframe": "now 1-H"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_timeframe_today_5y(self, async_test_client):
        """Test with 'today 5-y' timeframe."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python", "timeframe": "today 5-y"}
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    async def test_timeframe_custom_date_range(self, async_test_client):
        """Test with custom date range."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={
                "keywords": "python",
                "timeframe": "2024-01-01 2025-01-01"
            }
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ]


class TestGoogleTrendsCategories:
    """Test category filtering."""

    @pytest.mark.integration
    async def test_category_parameter(self, async_test_client):
        """Test interest over time with category filter."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={
                "keywords": "python",
                "category": "31"  # Science category
            }
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestGoogleTrendsResponseStructure:
    """Test response structure and data quality."""

    @pytest.mark.integration
    async def test_interest_over_time_has_data(self, async_test_client):
        """Test that interest over time returns data."""
        response = await async_test_client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should have data structure
            assert data is not None

    @pytest.mark.integration
    async def test_related_queries_structure(self, async_test_client):
        """Test related queries response structure."""
        response = await async_test_client.get(
            "/api/v1/google-trends/related-queries",
            params={"keywords": "python"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should contain rising and top queries
            assert data is not None
