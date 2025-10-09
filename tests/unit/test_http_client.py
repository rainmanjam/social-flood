"""
Tests for HTTP Client Manager with connection pooling.

This module tests the HTTPClientManager class and its functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx
from app.core.http_client import (
    HTTPClientManager,
    get_http_client_manager,
    set_http_client_manager,
    lifespan_manager
)


class TestHTTPClientManager:
    """Test cases for HTTPClientManager class."""

    @pytest.mark.unit
    def test_init(self):
        """Test HTTPClientManager initialization."""
        manager = HTTPClientManager()
        
        assert manager._clients == {}
        assert manager._client_lock is not None
        assert manager._stats["total_requests"] == 0
        assert manager._stats["successful_requests"] == 0
        assert manager._stats["failed_requests"] == 0
        assert manager._stats["average_response_time"] == 0.0

    @pytest.mark.unit
    async def test_get_client_creates_new_client(self, mock_settings):
        """Test that get_client creates a new client."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        client = await manager.get_client()
        
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert len(manager._clients) == 1
        assert "default" in manager._clients

    @pytest.mark.unit
    async def test_get_client_with_proxy(self, mock_settings):
        """Test that get_client can create client with proxy."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        proxy_url = "http://proxy.example.com:8080"
        client = await manager.get_client(proxy_url=proxy_url)
        
        assert client is not None
        assert proxy_url in manager._clients
        assert len(manager._clients) == 1

    @pytest.mark.unit
    async def test_get_client_reuses_existing(self, mock_settings):
        """Test that get_client reuses existing clients."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Get client first time
        client1 = await manager.get_client()
        pool_misses_1 = manager._stats["connection_pool_misses"]
        
        # Get client second time
        client2 = await manager.get_client()
        pool_hits = manager._stats["connection_pool_hits"]
        
        # Should be same client
        assert client1 is client2
        assert len(manager._clients) == 1
        assert pool_hits == 1

    @pytest.mark.unit
    async def test_get_client_different_proxies_different_clients(self, mock_settings):
        """Test that different proxy URLs create different clients."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        client1 = await manager.get_client(proxy_url="http://proxy1.com:8080")
        client2 = await manager.get_client(proxy_url="http://proxy2.com:8080")
        
        assert client1 is not client2
        assert len(manager._clients) == 2

    @pytest.mark.unit
    async def test_make_request_success(self, mock_settings):
        """Test successful HTTP request."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Mock the HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"success": True, "data": "test"}
        mock_response.text = '{"success": true, "data": "test"}'
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            result = await manager.make_request(
                url="https://api.example.com/test",
                method="GET",
                params={"param1": "value1"}
            )
        
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["content"] == {"success": True, "data": "test"}
        assert manager._stats["total_requests"] == 1
        assert manager._stats["successful_requests"] == 1

    @pytest.mark.unit
    async def test_make_request_failure(self, mock_settings):
        """Test failed HTTP request."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Mock the HTTP client to raise an exception
        with patch.object(
            httpx.AsyncClient,
            'request',
            side_effect=httpx.RequestError("Connection failed")
        ):
            result = await manager.make_request(
                url="https://api.example.com/test",
                method="GET"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert manager._stats["total_requests"] == 1
        assert manager._stats["failed_requests"] == 1

    @pytest.mark.unit
    async def test_make_request_non_200_status(self, mock_settings):
        """Test HTTP request with non-200 status code."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"error": "Not Found"}
        mock_response.text = '{"error": "Not Found"}'
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            result = await manager.make_request(
                url="https://api.example.com/test",
                method="GET"
            )
        
        assert result["success"] is False
        assert result["status_code"] == 404
        assert manager._stats["failed_requests"] == 1

    @pytest.mark.unit
    async def test_make_request_timeout(self, mock_settings):
        """Test HTTP request timeout handling."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        with patch.object(
            httpx.AsyncClient,
            'request',
            side_effect=httpx.TimeoutException("Request timeout")
        ):
            result = await manager.make_request(
                url="https://api.example.com/test",
                method="GET"
            )
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower()
        assert manager._stats["failed_requests"] == 1

    @pytest.mark.unit
    async def test_make_request_non_json_response(self, mock_settings):
        """Test HTTP request with non-JSON response."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body>Test</body></html>"
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            result = await manager.make_request(
                url="https://api.example.com/test",
                method="GET"
            )
        
        assert result["success"] is True
        assert result["content"] == "<html><body>Test</body></html>"

    @pytest.mark.unit
    async def test_batch_requests_sequential_when_disabled(self, mock_settings):
        """Test batch requests fall back to sequential when disabled."""
        mock_settings.BATCH_PROCESSING_ENABLED = False
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'
        
        requests = [
            {"url": "https://api.example.com/1", "method": "GET"},
            {"url": "https://api.example.com/2", "method": "GET"},
            {"url": "https://api.example.com/3", "method": "GET"},
        ]
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            results = await manager.batch_requests(requests)
        
        assert len(results) == 3
        assert all(r["success"] for r in results)

    @pytest.mark.unit
    async def test_batch_requests_parallel_when_enabled(self, mock_settings):
        """Test batch requests execute in parallel when enabled."""
        mock_settings.BATCH_PROCESSING_ENABLED = True
        mock_settings.MAX_CONCURRENT_BATCHES = 2
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'
        
        requests = [
            {"url": f"https://api.example.com/{i}", "method": "GET"}
            for i in range(5)
        ]
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            results = await manager.batch_requests(requests, max_concurrent=2)
        
        assert len(results) == 5
        assert all(r["success"] for r in results)

    @pytest.mark.unit
    async def test_batch_requests_handles_exceptions(self, mock_settings):
        """Test that batch requests handle exceptions gracefully."""
        mock_settings.BATCH_PROCESSING_ENABLED = True
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Make some requests fail
        async def mock_request(*args, **kwargs):
            url = kwargs.get('url', '')
            if '2' in url:
                raise httpx.RequestError("Failed request")
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {"success": True}
            mock_response.text = '{"success": true}'
            return mock_response
        
        requests = [
            {"url": f"https://api.example.com/{i}", "method": "GET"}
            for i in range(4)
        ]
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=mock_request):
            results = await manager.batch_requests(requests)
        
        assert len(results) == 4
        # Some should succeed, some should fail
        successes = sum(1 for r in results if r["success"])
        failures = sum(1 for r in results if not r["success"])
        assert successes > 0
        assert failures > 0

    @pytest.mark.unit
    def test_update_response_time_stats(self, mock_settings):
        """Test response time statistics update."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # First request
        manager._stats["total_requests"] = 1
        manager._update_response_time_stats(1.0)
        assert manager._stats["average_response_time"] == 1.0
        
        # Second request
        manager._stats["total_requests"] = 2
        manager._update_response_time_stats(2.0)
        assert manager._stats["average_response_time"] == 1.5
        
        # Third request
        manager._stats["total_requests"] = 3
        manager._update_response_time_stats(3.0)
        assert manager._stats["average_response_time"] == 2.0

    @pytest.mark.unit
    def test_get_stats(self, mock_settings):
        """Test getting client statistics."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        manager._stats["total_requests"] = 10
        manager._stats["successful_requests"] = 8
        manager._stats["failed_requests"] = 2
        manager._stats["connection_pool_hits"] = 7
        manager._stats["connection_pool_misses"] = 3
        
        stats = manager.get_stats()
        
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["failed_requests"] == 2
        assert stats["active_clients"] == 0
        assert stats["connection_pool_efficiency"] == 70.0

    @pytest.mark.unit
    async def test_close_all_clients(self, mock_settings):
        """Test closing all HTTP clients."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Create a few clients
        client1 = await manager.get_client()
        client2 = await manager.get_client(proxy_url="http://proxy.example.com:8080")
        
        assert len(manager._clients) == 2
        
        # Close all clients
        await manager.close_all_clients()
        
        assert len(manager._clients) == 0


class TestGlobalClientManager:
    """Test cases for global HTTP client manager functions."""

    @pytest.mark.unit
    def test_get_http_client_manager(self):
        """Test getting global HTTP client manager."""
        manager = get_http_client_manager()
        assert isinstance(manager, HTTPClientManager)

    @pytest.mark.unit
    def test_set_http_client_manager(self):
        """Test setting global HTTP client manager."""
        custom_manager = HTTPClientManager()
        set_http_client_manager(custom_manager)
        
        retrieved = get_http_client_manager()
        assert retrieved is custom_manager

    @pytest.mark.unit
    async def test_lifespan_manager(self, mock_settings):
        """Test lifespan manager context."""
        # Create a custom manager for testing
        test_manager = HTTPClientManager()
        test_manager.settings = mock_settings
        set_http_client_manager(test_manager)
        
        # Create some clients
        await test_manager.get_client()
        await test_manager.get_client(proxy_url="http://proxy.example.com:8080")
        
        assert len(test_manager._clients) == 2
        
        # Use lifespan manager
        async with lifespan_manager() as manager:
            assert isinstance(manager, HTTPClientManager)
            assert len(manager._clients) == 2
        
        # After context exit, clients should be closed
        # Note: This depends on whether set_http_client_manager
        # is properly called, so we check the test_manager directly
        assert len(test_manager._clients) == 0


class TestHTTPClientIntegration:
    """Integration tests for HTTP client manager."""

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_real_http_request(self, mock_settings):
        """Test making a real HTTP request to a public API."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        # Use a reliable public API for testing
        result = await manager.make_request(
            url="https://httpbin.org/get",
            method="GET",
            params={"test": "value"}
        )
        
        assert result["success"] is True
        assert result["status_code"] == 200
        assert "content" in result
        assert manager._stats["total_requests"] > 0

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_real_batch_requests(self, mock_settings):
        """Test making real batch HTTP requests."""
        mock_settings.BATCH_PROCESSING_ENABLED = True
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        requests = [
            {"url": "https://httpbin.org/get", "method": "GET", "params": {"id": i}}
            for i in range(3)
        ]
        
        results = await manager.batch_requests(requests, max_concurrent=2)
        
        assert len(results) == 3
        assert all(r["success"] for r in results)

    @pytest.mark.integration
    async def test_connection_pooling_efficiency(self, mock_settings):
        """Test that connection pooling improves efficiency."""
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            # Make multiple requests to same endpoint
            for _ in range(10):
                await manager.make_request(
                    url="https://api.example.com/test",
                    method="GET"
                )
        
        stats = manager.get_stats()
        
        # Should have reused connections (high hit rate)
        assert stats["connection_pool_hits"] > 0
        assert stats["connection_pool_efficiency"] > 50.0


# ============================================================================
# Performance Tests
# ============================================================================

class TestHTTPClientPerformance:
    """Performance tests for HTTP client manager."""

    @pytest.mark.performance
    @pytest.mark.slow
    async def test_concurrent_request_performance(self, mock_settings):
        """Benchmark concurrent request handling."""
        import time
        
        mock_settings.BATCH_PROCESSING_ENABLED = True
        mock_settings.MAX_CONCURRENT_BATCHES = 10
        manager = HTTPClientManager()
        manager.settings = mock_settings
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'
        
        # Simulate network delay
        async def delayed_request(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms simulated latency
            return mock_response
        
        requests = [
            {"url": f"https://api.example.com/{i}", "method": "GET"}
            for i in range(50)
        ]
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=delayed_request):
            start_time = time.time()
            results = await manager.batch_requests(requests, max_concurrent=10)
            elapsed = time.time() - start_time
        
        # With 10 concurrent requests and 50 total requests,
        # should take roughly 5 batches * 0.1s = 0.5s
        # Allow some overhead, so check < 1.0s
        assert elapsed < 1.0
        assert len(results) == 50
        assert all(r["success"] for r in results)
