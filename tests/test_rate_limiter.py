import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.rate_limiter import (
    RateLimiter,
    RateLimitMiddleware,
    rate_limit,
    limiter,
    start_cleanup_task,
    _rate_limit_store
)


class TestRateLimiter:
    """Test cases for RateLimiter class."""

    def setup_method(self):
        """Clear the rate limit store before each test."""
        _rate_limit_store.clear()

    def teardown_method(self):
        """Clear the rate limit store after each test."""
        _rate_limit_store.clear()

    def test_init_with_settings(self):
        """Test RateLimiter initialization with settings."""
        mock_settings = MagicMock()
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_settings.RATE_LIMIT_REQUESTS = 50
        mock_settings.RATE_LIMIT_TIMEFRAME = 1800

        limiter = RateLimiter(settings=mock_settings)

        assert limiter.enabled is True
        assert limiter.requests == 50
        assert limiter.timeframe == 1800

    def test_init_defaults(self):
        """Test RateLimiter initialization with defaults."""
        with patch('app.core.rate_limiter.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 100
            mock_settings.RATE_LIMIT_TIMEFRAME = 3600
            mock_get_settings.return_value = mock_settings

            limiter = RateLimiter()

            assert limiter.enabled is True
            assert limiter.requests == 100
            assert limiter.timeframe == 3600

    def test_init_disabled(self):
        """Test RateLimiter initialization when disabled."""
        mock_settings = MagicMock()
        mock_settings.RATE_LIMIT_ENABLED = False
        mock_settings.RATE_LIMIT_REQUESTS = 100
        mock_settings.RATE_LIMIT_TIMEFRAME = 3600

        limiter = RateLimiter(settings=mock_settings)

        assert limiter.enabled is False

    @pytest.mark.asyncio
    async def test_get_rate_limit_key_with_api_key(self):
        """Test getting rate limit key with API key."""
        limiter = RateLimiter()

        # Mock request with API key
        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', new_callable=AsyncMock) as mock_get_key:
            mock_get_key.return_value = "test_api_key"

            key = await limiter._get_rate_limit_key(mock_request)
            assert key == "rate_limit:api_key:test_api_key"

    @pytest.mark.asyncio
    async def test_get_rate_limit_key_fallback_to_ip(self):
        """Test getting rate limit key falling back to IP."""
        limiter = RateLimiter()

        # Mock request without API key
        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "192.168.1.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            key = await limiter._get_rate_limit_key(mock_request)
            assert key == "rate_limit:ip:192.168.1.1"

    @pytest.mark.asyncio
    async def test_get_rate_limit_key_unknown_client(self):
        """Test getting rate limit key with unknown client."""
        limiter = RateLimiter()

        # Mock request with no client
        mock_request = MagicMock()
        mock_request.client = None

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            key = await limiter._get_rate_limit_key(mock_request)
            assert key == "rate_limit:ip:unknown"

    @pytest.mark.asyncio
    async def test_is_rate_limited_disabled(self):
        """Test rate limiting when disabled."""
        mock_settings = MagicMock()
        mock_settings.RATE_LIMIT_ENABLED = False
        limiter = RateLimiter(settings=mock_settings)

        mock_request = MagicMock()
        is_limited, info = await limiter.is_rate_limited(mock_request)

        assert is_limited is False
        assert info == {}

    @pytest.mark.asyncio
    async def test_is_rate_limited_first_request(self):
        """Test rate limiting for first request."""
        limiter = RateLimiter(requests=2, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            is_limited, info = await limiter.is_rate_limited(mock_request)

            assert is_limited is False
            assert info["current"] == 1
            assert info["limit"] == 2
            assert "headers" in info

    @pytest.mark.asyncio
    async def test_is_rate_limited_under_limit(self):
        """Test rate limiting when under the limit."""
        limiter = RateLimiter(requests=3, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await limiter.is_rate_limited(mock_request)

            # Second request
            is_limited, info = await limiter.is_rate_limited(mock_request)

            assert is_limited is False
            assert info["current"] == 2
            assert info["limit"] == 3

    @pytest.mark.asyncio
    async def test_is_rate_limited_at_limit(self):
        """Test rate limiting when at the limit."""
        limiter = RateLimiter(requests=2, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await limiter.is_rate_limited(mock_request)

            # Second request (at limit)
            is_limited, info = await limiter.is_rate_limited(mock_request)

            assert is_limited is False
            assert info["current"] == 2
            assert info["limit"] == 2

    @pytest.mark.asyncio
    async def test_is_rate_limited_over_limit(self):
        """Test rate limiting when over the limit."""
        limiter = RateLimiter(requests=2, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await limiter.is_rate_limited(mock_request)

            # Second request
            await limiter.is_rate_limited(mock_request)

            # Third request (over limit)
            is_limited, info = await limiter.is_rate_limited(mock_request)

            assert is_limited is True
            assert info["current"] == 3
            assert info["limit"] == 2

    @pytest.mark.asyncio
    async def test_is_rate_limited_window_expired(self):
        """Test rate limiting when window expires."""
        limiter = RateLimiter(requests=2, timeframe=1)  # 1 second window

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await limiter.is_rate_limited(mock_request)

            # Wait for window to expire
            await asyncio.sleep(1.1)

            # Second request (should reset window)
            is_limited, info = await limiter.is_rate_limited(mock_request)

            assert is_limited is False
            assert info["current"] == 1
            assert info["limit"] == 2

    def test_get_rate_limit_headers(self):
        """Test rate limit headers generation."""
        limiter = RateLimiter()

        # Mock time.time to return a fixed value
        fixed_time = 1000000000.0
        window_start = fixed_time
        
        with patch('app.core.rate_limiter.time.time', return_value=fixed_time):
            headers = limiter._get_rate_limit_headers(5, 10, 3600, window_start)

        assert headers["headers"]["X-RateLimit-Limit"] == "10"
        assert headers["headers"]["X-RateLimit-Remaining"] == "5"
        assert headers["headers"]["X-RateLimit-Reset"] == "3600"
        assert headers["current"] == 5
        assert headers["limit"] == 10
        assert headers["reset"] == 3600

    @pytest.mark.asyncio
    async def test_limit_disabled(self):
        """Test limit method when disabled."""
        mock_settings = MagicMock()
        mock_settings.RATE_LIMIT_ENABLED = False
        limiter = RateLimiter(settings=mock_settings)

        mock_request = MagicMock()
        mock_call_next = AsyncMock(return_value="response")

        result = await limiter.limit(mock_request, mock_call_next)

        assert result == "response"
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_limit_not_limited_middleware(self):
        """Test limit method as middleware when not rate limited."""
        limiter = RateLimiter(requests=5, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            result = await limiter.limit(mock_request, mock_call_next)

            assert result == mock_response
            # Check that headers were added
            assert mock_response.headers.__setitem__.called

    @pytest.mark.asyncio
    async def test_limit_rate_limited_middleware(self):
        """Test limit method as middleware when rate limited."""
        limiter = RateLimiter(requests=1, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request (not limited)
            await limiter.limit(mock_request)

            # Second request (limited) - should return 429 response
            result = await limiter.limit(mock_request, AsyncMock())

            assert isinstance(result, JSONResponse)
            assert result.status_code == 429

    @pytest.mark.asyncio
    async def test_limit_rate_limited_dependency(self):
        """Test limit method as dependency when rate limited."""
        limiter = RateLimiter(requests=1, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request (not limited)
            await limiter.limit(mock_request)

            # Second request (limited) - should raise exception
            with pytest.raises(Exception):  # RateLimitExceededError
                await limiter.limit(mock_request)


class TestRateLimitMiddleware:
    """Test cases for RateLimitMiddleware class."""

    def setup_method(self):
        """Clear the rate limit store before each test."""
        _rate_limit_store.clear()

    def teardown_method(self):
        """Clear the rate limit store after each test."""
        _rate_limit_store.clear()

    def test_init(self):
        """Test middleware initialization."""
        mock_app = MagicMock()
        middleware = RateLimitMiddleware(mock_app, requests=50, timeframe=1800)

        assert middleware.limiter.requests == 50
        assert middleware.limiter.timeframe == 1800

    @pytest.mark.asyncio
    async def test_dispatch_not_limited(self):
        """Test middleware dispatch when not rate limited."""
        mock_app = MagicMock()
        middleware = RateLimitMiddleware(mock_app, requests=5, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_rate_limited(self):
        """Test middleware dispatch when rate limited."""
        mock_app = MagicMock()
        middleware = RateLimitMiddleware(mock_app, requests=1, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await middleware.dispatch(mock_request, AsyncMock())

            # Second request (should be limited)
            result = await middleware.dispatch(mock_request, AsyncMock())

            assert isinstance(result, JSONResponse)
            assert result.status_code == 429


class TestGlobalFunctions:
    """Test cases for global functions and dependencies."""

    def setup_method(self):
        """Clear the rate limit store before each test."""
        _rate_limit_store.clear()

    def teardown_method(self):
        """Clear the rate limit store after each test."""
        _rate_limit_store.clear()

    @pytest.mark.asyncio
    async def test_rate_limit_dependency(self):
        """Test rate_limit dependency function."""
        # Create a limiter that's disabled for testing
        mock_settings = MagicMock()
        mock_settings.RATE_LIMIT_ENABLED = False
        test_limiter = RateLimiter(settings=mock_settings)

        # Patch the global limiter
        import app.core.rate_limiter
        original_limiter = app.core.rate_limiter.limiter
        app.core.rate_limiter.limiter = test_limiter

        try:
            mock_request = MagicMock()
            # Should not raise exception when disabled
            await rate_limit(mock_request)
        finally:
            # Restore original limiter
            app.core.rate_limiter.limiter = original_limiter

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self):
        """Test that cleanup task can be started."""
        # This is mainly to ensure the function doesn't crash
        try:
            start_cleanup_task()
            # If we get here without exception, the test passes
        except Exception as e:
            pytest.fail(f"start_cleanup_task() raised an exception: {e}")


class TestRateLimitStore:
    """Test cases for the in-memory rate limit store."""

    def setup_method(self):
        """Clear the rate limit store before each test."""
        _rate_limit_store.clear()

    def teardown_method(self):
        """Clear the rate limit store after each test."""
        _rate_limit_store.clear()

    @pytest.mark.asyncio
    async def test_store_persistence(self):
        """Test that the store persists data correctly."""
        limiter = RateLimiter(requests=3, timeframe=60)

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # First request
            await limiter.is_rate_limited(mock_request)
            assert len(_rate_limit_store) == 1
            key = list(_rate_limit_store.keys())[0]
            assert _rate_limit_store[key][0] == 1

            # Second request
            await limiter.is_rate_limited(mock_request)
            assert _rate_limit_store[key][0] == 2

    @pytest.mark.asyncio
    async def test_store_cleanup(self):
        """Test that expired entries can be cleaned up."""
        limiter = RateLimiter(requests=2, timeframe=1)  # 1 second window

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request.client = mock_client

        with patch('app.core.rate_limiter.get_current_api_key', side_effect=Exception("No API key")):
            # Make a request
            await limiter.is_rate_limited(mock_request)
            assert len(_rate_limit_store) == 1

            # Wait for window to expire
            await asyncio.sleep(1.1)

            # Manually trigger cleanup (simulate the cleanup task)
            now = time.time()
            expired_keys = []
            for key, (_, window_start) in _rate_limit_store.items():
                if now - window_start > 1:
                    expired_keys.append(key)

            for key in expired_keys:
                del _rate_limit_store[key]

            assert len(_rate_limit_store) == 0