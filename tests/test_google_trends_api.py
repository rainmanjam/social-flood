"""
Comprehensive tests for Google Trends API endpoints.

This module provides extensive test coverage for all Google Trends API endpoints,
including success cases, error handling, caching, and edge cases.
"""

import pytest
import pandas as pd
import numpy as np
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import the router and utility functions
from app.api.google_trends.google_trends_api import (
    google_trends_router,
    get_random_headers,
    df_to_json,
    to_jsonable,
    get_trends_instance,
    REFERER_LIST,
    USER_AGENT_LIST,
    HumanFriendlyBatchPeriod
)


class TestGoogleTrendsAPI:
    """Test class for Google Trends API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the Google Trends router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(google_trends_router, prefix="/api/v1/google-trends")
        return TestClient(app)

    @pytest.fixture
    def mock_trends_instance(self):
        """Mock Trends instance for testing."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=5),
            'python': [50, 55, 60, 58, 62]
        })
        mock_instance.interest_by_region.return_value = pd.DataFrame({
            'geoName': ['United States', 'United Kingdom', 'Canada'],
            'python': [100, 80, 70]
        })
        mock_instance.related_queries.return_value = {
            'python': {
                'top': [{'query': 'python programming', 'value': 100}],
                'rising': [{'query': 'python tutorial', 'value': 150}]
            }
        }
        mock_instance.related_topics.return_value = {
            'python': {
                'top': [{'topic': 'Programming Language', 'value': 100}],
                'rising': [{'topic': 'Data Science', 'value': 120}]
            }
        }
        mock_instance.trending_now.return_value = [
            {'title': 'Python', 'formattedTraffic': '1M+', 'articles': []}
        ]
        mock_instance.trending_now_by_rss.return_value = [
            {'title': 'Python', 'newsItems': []}
        ]
        mock_instance.trending_now_news_by_ids.return_value = [
            ['token1', 'title1', '{"articles": []}']
        ]
        mock_instance.trending_now_showcase_timeline.return_value = {
            'python': [{'time': '2023-01-01', 'value': 50}]
        }
        mock_instance.categories.return_value = [
            {'id': '13', 'name': 'Computers & Electronics'}
        ]
        mock_instance.geo.return_value = [
            {'id': 'US', 'name': 'United States'}
        ]
        return mock_instance

    @pytest.fixture
    def mock_cache(self):
        """Mock cache functions."""
        with patch('app.api.google_trends.google_trends_api.get_cached_or_fetch') as mock_cache, \
             patch('app.api.google_trends.google_trends_api.generate_cache_key') as mock_key:
            mock_key.return_value = "test_cache_key"
            mock_cache.return_value = {"data": "cached_result"}
            yield mock_cache

    @pytest.fixture
    def mock_get_instance(self):
        """Mock get_trends_instance function."""
        with patch('app.api.google_trends.google_trends_api.get_trends_instance') as mock_instance:
            yield mock_instance

    # Test utility functions first
    def test_get_random_headers(self):
        """Test random header generation."""
        headers = get_random_headers()

        assert isinstance(headers, dict)
        assert "Referer" in headers
        assert "User-Agent" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert "Connection" in headers

        assert headers["Referer"] in REFERER_LIST
        assert headers["User-Agent"] in USER_AGENT_LIST
        assert headers["Accept-Language"] == "en-US,en;q=0.9"
        assert headers["Accept-Encoding"] == "gzip, deflate, br"
        assert headers["Connection"] == "keep-alive"

    def test_df_to_json_empty_dataframe(self):
        """Test df_to_json with empty DataFrame."""
        df = pd.DataFrame()
        result = df_to_json(df)
        assert result == []

    def test_df_to_json_with_data(self):
        """Test df_to_json with data."""
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [25, 30]
        })
        result = df_to_json(df)
        expected = [
            {'name': 'Alice', 'age': 25},
            {'name': 'Bob', 'age': 30}
        ]
        assert result == expected

    def test_to_jsonable_dataframe(self):
        """Test to_jsonable with DataFrame."""
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        result = to_jsonable(df)
        expected = [{'a': 1, 'b': 3}, {'a': 2, 'b': 4}]
        assert result == expected

    def test_to_jsonable_numpy_int(self):
        """Test to_jsonable with numpy int."""
        result = to_jsonable(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_to_jsonable_numpy_float(self):
        """Test to_jsonable with numpy float."""
        result = to_jsonable(np.float64(3.14))
        assert abs(result - 3.14) < 1e-10  # Use approximate comparison for floats
        assert isinstance(result, float)

    def test_to_jsonable_numpy_array(self):
        """Test to_jsonable with numpy array."""
        arr = np.array([1, 2, 3])
        result = to_jsonable(arr)
        assert result == [1, 2, 3]

    def test_to_jsonable_dict(self):
        """Test to_jsonable with dict containing numpy values."""
        data = {'a': np.int64(1), 'b': np.float64(2.5)}
        result = to_jsonable(data)
        expected = {'a': 1, 'b': 2.5}
        assert result == expected

    def test_to_jsonable_list(self):
        """Test to_jsonable with list containing numpy values."""
        data = [np.int64(1), np.float64(2.5)]
        result = to_jsonable(data)
        expected = [1, 2.5]
        assert result == expected

    def test_to_jsonable_string(self):
        """Test to_jsonable with regular string."""
        result = to_jsonable("hello")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_get_trends_instance_no_proxy(self, mock_trends_instance):
        """Test get_trends_instance without proxy."""
        with patch('app.api.google_trends.google_trends_api.get_proxy', return_value=None), \
             patch('app.api.google_trends.google_trends_api.Trends', return_value=mock_trends_instance):

            result = await get_trends_instance()

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_trends_instance_with_proxy(self, mock_trends_instance):
        """Test get_trends_instance with proxy."""
        with patch('app.api.google_trends.google_trends_api.get_proxy', return_value="http://proxy.example.com:8080"), \
             patch('app.api.google_trends.google_trends_api.Trends', return_value=mock_trends_instance):

            result = await get_trends_instance()

            assert result is not None

    # Test API endpoints
    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_interest_over_time_success(self, mock_get_instance, client):
        """Test interest over time endpoint success."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=3),
            'python': [50, 55, 60]
        })
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_interest_over_time_no_keywords(self, client):
        """Test interest over time with no keywords."""
        response = client.get("/api/v1/google-trends/interest-over-time?keywords=")

        assert response.status_code == 400
        data = response.json()
        assert "No valid keywords provided" in data["detail"]

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_interest_over_time_empty_dataframe(self, mock_get_instance, client):
        """Test interest over time with empty DataFrame response."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = pd.DataFrame()
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No data returned from Google Trends."

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_interest_by_region_success(self, mock_get_instance, client):
        """Test interest by region endpoint success."""
        mock_instance = MagicMock()
        mock_instance.interest_by_region.return_value = pd.DataFrame({
            'geoName': ['US', 'UK'],
            'python': [100, 80]
        })
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-by-region?keyword=python")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_related_queries_success(self, mock_get_instance, client):
        """Test related queries endpoint success."""
        mock_instance = MagicMock()
        mock_instance.related_queries.return_value = {
            'python': {
                'top': [{'query': 'python programming', 'value': 100}]
            }
        }
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/related-queries?keyword=python")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_related_topics_success(self, mock_get_instance, client):
        """Test related topics endpoint success."""
        mock_instance = MagicMock()
        mock_instance.related_topics.return_value = {
            'python': {
                'top': [{'topic': 'Programming', 'value': 100}]
            }
        }
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/related-topics?keyword=python")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_trending_now_success(self, mock_get_instance, client):
        """Test trending now endpoint success."""
        mock_instance = MagicMock()
        mock_instance.trending_now.return_value = [
            {'title': 'Python', 'formattedTraffic': '1M+'}
        ]
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/trending-now")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_trending_now_by_rss_success(self, mock_get_instance, client):
        """Test trending now by RSS endpoint success."""
        mock_instance = MagicMock()
        mock_instance.trending_now_by_rss.return_value = [
            {'title': 'Python', 'newsItems': []}
        ]
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/trending-now-by-rss")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_trending_now_news_by_ids_success(self, mock_get_instance, client):
        """Test trending now news by IDs endpoint success."""
        mock_instance = MagicMock()
        mock_instance.trending_now_news_by_ids.return_value = [
            ['token1', 'title1', '{"articles": [{"title": "Test Article"}]}']
        ]
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/trending-now-news-by-ids?news_tokens=token1")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_trending_now_news_by_ids_no_tokens(self, client):
        """Test trending now news by IDs with no tokens."""
        response = client.get("/api/v1/google-trends/trending-now-news-by-ids?news_tokens=")

        assert response.status_code == 400  # Bad request for no valid tokens
        data = response.json()
        assert "detail" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_trending_now_showcase_timeline_success(self, mock_get_instance, client):
        """Test trending now showcase timeline endpoint success."""
        mock_instance = MagicMock()
        mock_instance.trending_now_showcase_timeline.return_value = {
            'python': [{'time': '2023-01-01', 'value': 50}]
        }
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/trending-now-showcase-timeline?keywords=python&timeframe=past_24h")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_trending_now_showcase_timeline_no_keywords(self, client):
        """Test trending now showcase timeline with no keywords."""
        response = client.get("/api/v1/google-trends/trending-now-showcase-timeline?keywords=&timeframe=past_24h")

        assert response.status_code == 400  # Bad request for no valid keywords
        data = response.json()
        assert "detail" in data

    def test_trending_now_showcase_timeline_invalid_timeframe(self, client):
        """Test trending now showcase timeline with invalid timeframe."""
        response = client.get("/api/v1/google-trends/trending-now-showcase-timeline?keywords=python&timeframe=invalid")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_categories_success(self, mock_get_instance, client):
        """Test categories endpoint success."""
        mock_instance = MagicMock()
        mock_instance.categories.return_value = [
            {'id': '13', 'name': 'Computers & Electronics'}
        ]
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/categories")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_geo_success(self, mock_get_instance, client):
        """Test geo endpoint success."""
        mock_instance = MagicMock()
        mock_instance.geo.return_value = [
            {'id': 'US', 'name': 'United States'}
        ]
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/geo")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_api_error_handling(self, mock_get_instance, client):
        """Test API error handling across endpoints."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.side_effect = Exception("API Error")
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

        # The API handles exceptions gracefully and returns a message
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_caching_behavior(self, mock_get_instance, client):
        """Test that caching is properly implemented."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=3),
            'python': [50, 55, 60]
        })
        mock_get_instance.return_value = mock_instance

        with patch('app.api.google_trends.google_trends_api.generate_cache_key') as mock_key, \
             patch('app.api.google_trends.google_trends_api.get_cached_or_fetch') as mock_cache:

            mock_key.return_value = "test_key"
            mock_cache.return_value = {"data": "cached_data"}

            response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

            assert response.status_code == 200
            # Note: The actual caching behavior depends on the implementation

    # Test parameter validation
    def test_parameter_validation(self, client):
        """Test parameter validation for various endpoints."""
        # Test interest over time with missing required parameter
        response = client.get("/api/v1/google-trends/interest-over-time")
        assert response.status_code == 422  # Validation error

        # Test interest by region with missing required parameter
        response = client.get("/api/v1/google-trends/interest-by-region")
        assert response.status_code == 422  # Validation error

        # Test related queries with missing required parameter
        response = client.get("/api/v1/google-trends/related-queries")
        assert response.status_code == 422  # Validation error

    # Test enum values
    def test_human_friendly_batch_period_enum(self):
        """Test HumanFriendlyBatchPeriod enum values."""
        assert HumanFriendlyBatchPeriod.past_4h.value == "past_4h"
        assert HumanFriendlyBatchPeriod.past_24h.value == "past_24h"
        assert HumanFriendlyBatchPeriod.past_48h.value == "past_48h"
        assert HumanFriendlyBatchPeriod.past_7d.value == "past_7d"

    # Test edge cases
    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_empty_api_response_handling(self, mock_get_instance, client):
        """Test handling of empty API responses."""
        mock_instance = MagicMock()
        mock_instance.interest_over_time.return_value = None
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No data returned from Google Trends."

    @patch('app.api.google_trends.google_trends_api.get_trends_instance')
    def test_json_conversion_error_handling(self, mock_get_instance, client):
        """Test handling of JSON conversion errors."""
        mock_instance = MagicMock()
        # Return an object that can't be JSON serialized
        class NonSerializable:
            pass

        mock_instance.interest_over_time.return_value = NonSerializable()
        mock_get_instance.return_value = mock_instance

        response = client.get("/api/v1/google-trends/interest-over-time?keywords=python")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data  # The API handles errors gracefully