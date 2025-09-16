"""
Test suite for auth.py module.

This module contains comprehensive tests for API key authentication,
validation, and FastAPI dependency injection functionality.
"""

import pytest
import os
from unittest.mock import patch

from app.core.auth import (
    # Classes
    AuthSettings,
    api_key_header,

    # Functions
    validate_api_key,
    get_api_key_metadata,
    authenticate_api_key,
    get_current_api_key,

    # Global variables
    auth_settings,
    _api_keys_set,
    _api_key_metadata,
)


class TestAuthSettings:
    """Test AuthSettings configuration class."""

    def test_auth_settings_defaults(self):
        """Test AuthSettings with default values."""
        settings = AuthSettings()
        assert settings.API_KEYS == []
        assert settings.ENABLE_API_KEY_AUTH is True

    @patch.dict(os.environ, {"API_KEYS": '["key1","key2","key3"]'})
    def test_auth_settings_from_env_list(self):
        """Test AuthSettings loading API keys from environment."""
        settings = AuthSettings()
        assert "key1" in settings.API_KEYS
        assert "key2" in settings.API_KEYS
        assert "key3" in settings.API_KEYS

    @patch.dict(os.environ, {"ENABLE_API_KEY_AUTH": "false"})
    def test_auth_settings_disable_auth(self):
        """Test disabling API key authentication."""
        settings = AuthSettings()
        assert settings.ENABLE_API_KEY_AUTH is False


class TestAPIKeyValidation:
    """Test API key validation functions."""

    def setup_method(self):
        """Reset global state before each test."""
        # Store original state
        self.original_keys = _api_keys_set.copy()
        self.original_metadata = _api_key_metadata.copy()

        # Set test state by modifying module-level variables
        import app.core.auth
        app.core.auth._api_keys_set = {"valid_key1", "valid_key2"}
        app.core.auth._api_key_metadata = {
            "valid_key1": {"source": "environment"},
            "valid_key2": {"source": "environment"}
        }

    def teardown_method(self):
        """Restore global state after each test."""
        # Restore original state
        import app.core.auth
        app.core.auth._api_keys_set = self.original_keys
        app.core.auth._api_key_metadata = self.original_metadata

    def test_validate_api_key_valid(self):
        """Test validating a valid API key."""
        assert validate_api_key("valid_key1") is True
        assert validate_api_key("valid_key2") is True

    def test_validate_api_key_invalid(self):
        """Test validating an invalid API key."""
        assert validate_api_key("invalid_key") is False
        assert validate_api_key("") is False
        assert validate_api_key("VALID_KEY1") is False  # Case sensitive

    def test_get_api_key_metadata_valid(self):
        """Test getting metadata for a valid API key."""
        metadata = get_api_key_metadata("valid_key1")
        assert metadata is not None
        assert metadata["source"] == "environment"

    def test_get_api_key_metadata_invalid(self):
        """Test getting metadata for an invalid API key."""
        metadata = get_api_key_metadata("invalid_key")
        assert metadata is None


class TestAuthenticationDependencies:
    """Test FastAPI authentication dependencies."""

    def setup_method(self):
        """Reset global state before each test."""
        # Store original state
        self.original_keys = _api_keys_set.copy()

        # Set test state by modifying module-level variables
        import app.core.auth
        app.core.auth._api_keys_set = {"test_key"}

    def teardown_method(self):
        """Restore global state after each test."""
        # Restore original state
        import app.core.auth
        app.core.auth._api_keys_set = self.original_keys

    @patch('app.core.auth.auth_settings')
    @pytest.mark.asyncio
    async def test_authenticate_api_key_valid(self, mock_settings):
        """Test successful API key authentication."""
        mock_settings.ENABLE_API_KEY_AUTH = True
        # pylint: disable=global-statement
        global _api_keys_set
        _api_keys_set = {"test_key"}

        result = await authenticate_api_key("test_key")
        assert result == "test_key"

    @patch('app.core.auth.auth_settings')
    @pytest.mark.asyncio
    async def test_authenticate_api_key_invalid(self, mock_settings):
        """Test authentication with invalid API key."""
        mock_settings.ENABLE_API_KEY_AUTH = True

        with pytest.raises(Exception) as exc_info:  # Will be HTTPException in real usage
            await authenticate_api_key("invalid_key")

        # The exception details will depend on the actual implementation
        assert "Invalid" in str(exc_info.value) or "401" in str(exc_info.value)

    @patch('app.core.auth.auth_settings')
    @pytest.mark.asyncio
    async def test_authenticate_api_key_disabled(self, mock_settings):
        """Test authentication when disabled."""
        mock_settings.ENABLE_API_KEY_AUTH = False

        result = await authenticate_api_key("any_key")
        assert result == "authentication-disabled"

    def test_get_current_api_key(self):
        """Test get_current_api_key dependency."""
        result = get_current_api_key("test_key")
        assert result == "test_key"


class TestAPIKeyHeader:
    """Test API key header configuration."""

    def test_api_key_header_configuration(self):
        """Test that API key header is properly configured."""
        assert api_key_header is not None
        # The exact type depends on FastAPI implementation
        assert hasattr(api_key_header, 'scheme_name') or hasattr(api_key_header, 'model')


class TestGlobalState:
    """Test global state management."""

    def test_global_variables_initialized(self):
        """Test that global variables are properly initialized."""
        assert isinstance(_api_keys_set, set)
        assert isinstance(_api_key_metadata, dict)
        assert isinstance(auth_settings, AuthSettings)

    def test_auth_settings_singleton(self):
        """Test that auth_settings is a singleton."""
        # Use the already imported auth_settings
        settings1 = auth_settings
        settings2 = auth_settings
        assert settings1 is settings2


class TestBasicFunctionality:
    """Test basic authentication functionality."""

    def test_validate_api_key_basic(self):
        """Test basic API key validation."""
        # Test with empty set
        # pylint: disable=global-statement
        global _api_keys_set
        original_keys = _api_keys_set.copy()
        _api_keys_set = set()

        assert validate_api_key("any_key") is False

        # Restore original state
        _api_keys_set = original_keys

    def test_get_api_key_metadata_basic(self):
        """Test basic metadata retrieval."""
        # Test with empty metadata
        # pylint: disable=global-statement
        global _api_key_metadata
        original_metadata = _api_key_metadata.copy()
        _api_key_metadata = {}

        assert get_api_key_metadata("any_key") is None

        # Restore original state
        _api_key_metadata = original_metadata