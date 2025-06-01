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
    
    # Security
    SECRET_KEY: str = "development-secret-key-change-in-production"
    X_BEARER_TOKEN: Optional[str] = None
    
    # Google API credentials
    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = None
    GOOGLE_ADS_CLIENT_ID: Optional[str] = None
    GOOGLE_ADS_CLIENT_SECRET: Optional[str] = None
    GOOGLE_ADS_REFRESH_TOKEN: Optional[str] = None
    
    # Application settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Social Flood"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "API for social media data aggregation and analysis"
    
    @field_validator("API_KEYS", mode="before")
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
    
    This function is cached to avoid loading the settings multiple times.
    
    Returns:
        Settings: The application settings
    """
    return Settings()


# Global settings instance for direct imports
settings = get_settings()
