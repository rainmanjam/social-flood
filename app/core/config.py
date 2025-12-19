"""
Configuration settings for the Social Flood application.

This module provides a centralized way to access configuration settings
from environment variables using Pydantic's BaseSettings.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings
import os
from functools import lru_cache

# Import version from version file
try:
    from app.__version__ import __version__ as app_version
except ImportError:
    app_version = "0.1.0"  # Fallback version


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    This class uses Pydantic's BaseSettings to load and validate
    configuration settings from environment variables.
    """
    # API settings
    API_KEYS: List[str] = []
    ENABLE_API_KEY_AUTH: bool = True
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_TIMEFRAME: int = 3600  # seconds
    
    # Caching
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 3600  # seconds
    REDIS_URL: Optional[RedisDsn] = None
    
    # Database
    DATABASE_URL: Optional[PostgresDsn] = None
    
    # Proxy settings
    ENABLE_PROXY: bool = False
    PROXY_URL: Optional[str] = None
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Autocomplete settings
    AUTOCOMPLETE_MAX_PARALLEL_REQUESTS: int = 10
    AUTOCOMPLETE_REQUEST_TIMEOUT: int = 30
    AUTOCOMPLETE_MAX_RETRIES: int = 3
    AUTOCOMPLETE_RETRY_DELAY: float = 1.0
    
    # Connection Pooling settings
    HTTP_CONNECTION_POOL_SIZE: int = 20
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 10
    HTTP_MAX_CONNECTIONS_PER_HOST: int = 5
    HTTP_CONNECTION_TIMEOUT: float = 10.0
    HTTP_READ_TIMEOUT: float = 30.0
    
    # Batch Processing settings
    BATCH_PROCESSING_ENABLED: bool = True
    BATCH_SIZE: int = 50
    BATCH_TIMEOUT: float = 60.0
    MAX_CONCURRENT_BATCHES: int = 3
    
    # Input Sanitization settings
    INPUT_SANITIZATION_ENABLED: bool = True
    MAX_QUERY_LENGTH: int = 200
    ALLOWED_CHARACTERS_PATTERN: str = r"^[a-zA-Z0-9\s\-\.\,\?\!\(\)\[\]\{\}\'\"]+$"
    BLOCK_SUSPICIOUS_PATTERNS: bool = True
    SUSPICIOUS_PATTERNS: List[str] = ["<script", "javascript:", "onload=", "onerror=", "eval(", "alert("]
    
    # Response Metadata settings
    RESPONSE_METADATA_ENABLED: bool = True
    INCLUDE_REQUEST_TIMING: bool = True
    INCLUDE_CONNECTION_INFO: bool = True
    INCLUDE_CACHE_INFO: bool = True
    INCLUDE_RATE_LIMIT_INFO: bool = True
    
    # API Keys (for backward compatibility)
    API_KEY: Optional[str] = None
    
    # Proxy settings (for backward compatibility)
    PROXY_URLS: Optional[str] = None
    
    # Twitter API settings (for backward compatibility)
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET_KEY: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = None
    TWITTER_BEARER_TOKEN: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "development-secret-key-change-in-production"
    X_BEARER_TOKEN: Optional[str] = None
    
    # Application settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Social Flood"
    VERSION: str = app_version  # Use version from __version__.py
    DESCRIPTION: str = "API for social media data aggregation and analysis"
    
    @field_validator("API_KEYS", mode="before")
    @classmethod
    def assemble_api_keys(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parse API_KEYS from string to list if needed.
        
        Args:
            v: The API_KEYS value from environment
            
        Returns:
            List[str]: List of API keys
        """
        if isinstance(v, str) and v:
            return [key.strip() for key in v.split(",") if key.strip()]
        if isinstance(v, list):
            return v
        return []
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parse CORS_ORIGINS from string to list if needed.
        
        Args:
            v: The CORS_ORIGINS value from environment
            
        Returns:
            List[str]: List of allowed origins
        """
        if isinstance(v, str) and v:
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return []
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_file_encoding": "utf-8"
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings.

    This function is cached using @lru_cache to avoid loading settings
    multiple times. The cache ensures that environment variables are only
    parsed once at startup, improving performance.

    Caching Behavior:
        - Settings are loaded once on first call
        - Subsequent calls return the cached instance
        - Use reload_settings() to force a refresh

    Returns:
        Settings: The application settings instance

    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.ENVIRONMENT)
        'development'
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings by clearing the cache and creating a new instance.

    This function clears the lru_cache and reloads settings from
    environment variables. Useful for runtime configuration updates
    or testing scenarios.

    Note:
        This function also updates the module-level 'settings' variable.
        Any code holding references to the old settings instance will
        not see the updated values - they should call get_settings() again.

    Returns:
        Settings: The newly loaded settings instance

    Example:
        >>> from app.core.config import reload_settings
        >>> import os
        >>> os.environ['DEBUG'] = 'true'
        >>> settings = reload_settings()
        >>> assert settings.DEBUG == True
    """
    global settings
    get_settings.cache_clear()
    settings = get_settings()
    return settings


def is_settings_cached() -> bool:
    """
    Check if settings are currently cached.

    Returns:
        bool: True if settings are cached, False otherwise

    Example:
        >>> from app.core.config import is_settings_cached, get_settings
        >>> get_settings.cache_clear()
        >>> assert is_settings_cached() == False
        >>> _ = get_settings()
        >>> assert is_settings_cached() == True
    """
    cache_info = get_settings.cache_info()
    return cache_info.hits > 0 or cache_info.currsize > 0


def get_settings_cache_info() -> dict:
    """
    Get cache statistics for the settings.

    Returns:
        dict: Cache info including hits, misses, maxsize, currsize

    Example:
        >>> from app.core.config import get_settings_cache_info
        >>> info = get_settings_cache_info()
        >>> print(f"Cache hits: {info['hits']}")
    """
    cache_info = get_settings.cache_info()
    return {
        "hits": cache_info.hits,
        "misses": cache_info.misses,
        "maxsize": cache_info.maxsize,
        "currsize": cache_info.currsize
    }


# Global settings instance for direct imports
# This provides a convenient way to access settings without calling get_settings()
# Note: Use get_settings() in production code for better testability
settings = get_settings()
