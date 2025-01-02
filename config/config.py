# config/config.py
import os

ENABLE_CACHE = os.getenv('ENABLE_CACHE', 'false').lower() == 'true'
ENABLE_PROXY = os.getenv('ENABLE_PROXY', 'false').lower() == 'true'
ENABLE_RATE_LIMITING = os.getenv('ENABLE_RATE_LIMITING', 'false').lower() == 'true'

PROXY_URL = os.getenv('PROXY_URL', '')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/social_flood')

# Example of API keys from environment variables
GOOGLE_TRENDS_API_KEY = os.getenv('GOOGLE_TRENDS_API_KEY', '')
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY', '')
