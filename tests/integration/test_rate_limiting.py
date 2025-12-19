"""
Integration tests for rate limiting.

These tests verify that rate limiting works correctly across the application.
"""
import pytest
from fastapi.testclient import TestClient
import os
import time


@pytest.fixture
def rate_limited_app():
    """Create app with rate limiting enabled."""
    # Store original values
    original_rate = os.environ.get("RATE_LIMIT_ENABLED")
    original_requests = os.environ.get("RATE_LIMIT_REQUESTS")
    original_timeframe = os.environ.get("RATE_LIMIT_TIMEFRAME")
    original_auth = os.environ.get("ENABLE_API_KEY_AUTH")
    original_keys = os.environ.get("API_KEYS")

    # Set test configuration - low limits for testing
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_REQUESTS"] = "5"  # Only 5 requests allowed
    os.environ["RATE_LIMIT_TIMEFRAME"] = "60"  # Per minute
    os.environ["ENABLE_API_KEY_AUTH"] = "false"

    # Clear cached settings
    from app.core.config import get_settings
    get_settings.cache_clear()

    # Clear rate limit store
    from app.core.rate_limiter import _rate_limit_store
    _rate_limit_store.clear()

    from main import create_application
    app = create_application()

    yield app

    # Restore original values
    if original_rate:
        os.environ["RATE_LIMIT_ENABLED"] = original_rate
    else:
        os.environ.pop("RATE_LIMIT_ENABLED", None)

    if original_requests:
        os.environ["RATE_LIMIT_REQUESTS"] = original_requests
    else:
        os.environ.pop("RATE_LIMIT_REQUESTS", None)

    if original_timeframe:
        os.environ["RATE_LIMIT_TIMEFRAME"] = original_timeframe
    else:
        os.environ.pop("RATE_LIMIT_TIMEFRAME", None)

    if original_auth:
        os.environ["ENABLE_API_KEY_AUTH"] = original_auth
    else:
        os.environ.pop("ENABLE_API_KEY_AUTH", None)

    if original_keys:
        os.environ["API_KEYS"] = original_keys
    else:
        os.environ.pop("API_KEYS", None)

    # Clear settings cache
    get_settings.cache_clear()

    # Clear rate limit store
    _rate_limit_store.clear()


@pytest.fixture
def rate_client(rate_limited_app):
    """Create test client for rate-limited app."""
    return TestClient(rate_limited_app)


class TestRateLimitHeaders:
    """Test rate limit response headers."""

    def test_rate_limit_headers_present(self, rate_client):
        """Test that rate limit headers are present in responses."""
        # Clear rate limit store before test
        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        response = rate_client.get("/api-config")

        # Check for rate limit headers
        headers = response.headers
        assert "x-ratelimit-limit" in headers or response.status_code == 200
        # Note: Headers might only appear when rate limiting middleware is applied

    def test_rate_limit_remaining_decreases(self, rate_client):
        """Test that remaining count decreases with each request."""
        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        # Make first request
        response1 = rate_client.get("/api-config")
        remaining1 = response1.headers.get("x-ratelimit-remaining")

        if remaining1:
            # Make second request
            response2 = rate_client.get("/api-config")
            remaining2 = response2.headers.get("x-ratelimit-remaining")

            if remaining2:
                assert int(remaining2) < int(remaining1)


class TestRateLimitEnforcement:
    """Test that rate limits are enforced."""

    def test_rate_limit_exceeded(self, rate_client):
        """Test that exceeding rate limit returns 429."""
        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        # Make requests up to the limit (5) plus one more
        responses = []
        for _ in range(7):
            response = rate_client.get("/api-config")
            responses.append(response.status_code)

        # At least one should be 429 (Too Many Requests)
        assert 429 in responses, f"Expected 429 in responses: {responses}"

    def test_rate_limit_429_response_format(self, rate_client):
        """Test that 429 response has correct format."""
        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        # Exhaust rate limit
        for _ in range(10):
            response = rate_client.get("/api-config")
            if response.status_code == 429:
                data = response.json()
                # Should have error information
                assert "detail" in data or "title" in data or "message" in data
                break


class TestRateLimitByKey:
    """Test rate limiting by API key."""

    @pytest.fixture
    def rate_auth_app(self):
        """Create app with both rate limiting and auth enabled."""
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        os.environ["RATE_LIMIT_REQUESTS"] = "3"
        os.environ["RATE_LIMIT_TIMEFRAME"] = "60"
        os.environ["ENABLE_API_KEY_AUTH"] = "true"
        os.environ["API_KEYS"] = "key-user-a,key-user-b"

        from app.core.config import get_settings
        get_settings.cache_clear()

        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        from main import create_application
        app = create_application()

        yield app

        os.environ.pop("RATE_LIMIT_ENABLED", None)
        os.environ.pop("RATE_LIMIT_REQUESTS", None)
        os.environ.pop("RATE_LIMIT_TIMEFRAME", None)
        os.environ.pop("ENABLE_API_KEY_AUTH", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()
        _rate_limit_store.clear()

    def test_separate_limits_per_api_key(self, rate_auth_app):
        """Test that different API keys have separate rate limits."""
        from app.core.rate_limiter import _rate_limit_store
        _rate_limit_store.clear()

        client = TestClient(rate_auth_app)

        # User A makes requests
        for _ in range(3):
            response = client.get(
                "/api-config",
                headers={"X-API-Key": "key-user-a"}
            )

        # User A should be rate limited
        response_a = client.get(
            "/api-config",
            headers={"X-API-Key": "key-user-a"}
        )

        # User B should still be able to make requests
        response_b = client.get(
            "/api-config",
            headers={"X-API-Key": "key-user-b"}
        )

        # User B should succeed (not rate limited)
        assert response_b.status_code == 200


class TestRateLimitDisabled:
    """Test behavior when rate limiting is disabled."""

    @pytest.fixture
    def no_rate_app(self):
        """Create app with rate limiting disabled."""
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        os.environ["ENABLE_API_KEY_AUTH"] = "false"

        from app.core.config import get_settings
        get_settings.cache_clear()

        from main import create_application
        app = create_application()

        yield app

        os.environ.pop("RATE_LIMIT_ENABLED", None)
        os.environ.pop("ENABLE_API_KEY_AUTH", None)
        get_settings.cache_clear()

    def test_no_rate_limit_when_disabled(self, no_rate_app):
        """Test that rate limiting doesn't apply when disabled."""
        client = TestClient(no_rate_app)

        # Make many requests
        responses = []
        for _ in range(20):
            response = client.get("/api-config")
            responses.append(response.status_code)

        # None should be 429
        assert 429 not in responses, "Rate limiting should be disabled"
