# Google Services Integration

This document provides information on how to integrate with various Google services used by the Social Flood API.

## Overview of Google Services

The Social Flood API integrates with the following Google services:

1. **Google News** - Access and search news articles
2. **Google Trends** - Retrieve trending topics and search interest data
3. **Google Autocomplete** - Get search suggestions and keyword variations
4. **YouTube Transcripts** - Extract transcripts from YouTube videos
5. **Google Ads** - Access advertising data and keyword research (planned)

## Authentication and Credentials

### Google API Key

Some Google services require an API key for authentication. To obtain a Google API key:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "API Key"
5. Restrict the API key to only the services you need
6. Copy the API key and add it to your `.env` file

```
GOOGLE_API_KEY=your_api_key_here
```

### Google Ads API Credentials

Google Ads API requires OAuth 2.0 credentials:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "OAuth client ID"
5. Select "Web application" as the application type
6. Add authorized redirect URIs (e.g., `http://localhost:8000/auth/callback`)
7. Copy the client ID and client secret
8. Obtain a developer token from the [Google Ads API Center](https://ads.google.com/home/tools/manager-accounts/)
9. Generate a refresh token using the OAuth 2.0 flow
10. Add these credentials to your `.env` file

```
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
GOOGLE_ADS_CLIENT_ID=your_client_id
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
```

## Code Examples

### Setting Up Google Ads Client

```python
from app.core.config import get_settings

settings = get_settings()

# Check if Google Ads credentials are configured
if all([
    settings.GOOGLE_ADS_DEVELOPER_TOKEN,
    settings.GOOGLE_ADS_CLIENT_ID,
    settings.GOOGLE_ADS_CLIENT_SECRET,
    settings.GOOGLE_ADS_REFRESH_TOKEN
]):
    from google.ads.googleads.client import GoogleAdsClient
    
    # Create credentials dictionary
    credentials = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "use_proto_plus": True
    }
    
    # Initialize Google Ads client
    google_ads_client = GoogleAdsClient.load_from_dict(credentials)
else:
    raise ValueError("Google Ads credentials not fully configured")
```

### Making a Google News API Request

```python
import httpx
from app.core.config import get_settings

settings = get_settings()

async def search_google_news(query: str, country: str = "US", language: str = "en", max_results: int = 10):
    """
    Search Google News for articles matching the query.
    
    Args:
        query: The search query
        country: The country code (e.g., US, GB, CA)
        language: The language code (e.g., en, fr, es)
        max_results: Maximum number of results to return
        
    Returns:
        List of news articles
    """
    # Use proxy if configured
    proxy = None
    if settings.ENABLE_PROXY and settings.PROXY_URL:
        proxy = settings.PROXY_URL
    
    # Set up HTTP client
    async with httpx.AsyncClient(proxies=proxy) as client:
        # Construct the URL
        url = "https://news.google.com/rss/search"
        params = {
            "q": query,
            "hl": language,
            "gl": country,
            "ceid": f"{country}:{language}"
        }
        
        # Make the request
        response = await client.get(url, params=params)
        
        # Parse the response
        if response.status_code == 200:
            # Parse XML response
            # (Implementation details omitted for brevity)
            pass
        else:
            raise Exception(f"Failed to retrieve news: {response.status_code}")
```

### Using Google Autocomplete API

```python
import httpx
from app.core.config import get_settings

settings = get_settings()

async def get_autocomplete_suggestions(query: str, country: str = "US", language: str = "en"):
    """
    Get autocomplete suggestions from Google.
    
    Args:
        query: The search query
        country: The country code (e.g., US, GB, CA)
        language: The language code (e.g., en, fr, es)
        
    Returns:
        List of autocomplete suggestions
    """
    # Use proxy if configured
    proxy = None
    if settings.ENABLE_PROXY and settings.PROXY_URL:
        proxy = settings.PROXY_URL
    
    # Set up HTTP client
    async with httpx.AsyncClient(proxies=proxy) as client:
        # Construct the URL
        url = "https://www.google.com/complete/search"
        params = {
            "q": query,
            "client": "chrome",
            "hl": language,
            "gl": country
        }
        
        # Make the request
        response = await client.get(url, params=params)
        
        # Parse the response
        if response.status_code == 200:
            data = response.json()
            suggestions = data[1] if len(data) > 1 else []
            return suggestions
        else:
            raise Exception(f"Failed to retrieve suggestions: {response.status_code}")
```

## Rate Limits and Quotas

### Google News

Google News does not have an official API, and the Social Flood API uses web scraping techniques to extract data. Be aware that excessive requests may lead to temporary IP blocks.

### Google Trends

Google Trends does not have an official API, and the Social Flood API uses the unofficial `pytrends` library. Be mindful of the following limitations:

- Maximum of 5 keywords per request
- Maximum of 5 requests per minute per IP address

### Google Autocomplete

Google Autocomplete does not have an official API, and the Social Flood API uses direct requests to the autocomplete endpoint. Be mindful of the following limitations:

- Maximum of 10 requests per minute per IP address

### YouTube Transcripts

YouTube Transcripts API uses the `youtube-transcript-api` library, which has the following limitations:

- Maximum of 300 requests per day per IP address

### Google Ads API

Google Ads API has official quotas that vary by account type:

- Standard accounts: 10,000 operations per day
- Premium accounts: 100,000 operations per day

## Best Practices

1. **Use Caching**: Implement caching to reduce the number of requests to Google services
2. **Implement Rate Limiting**: Add rate limiting to prevent exceeding quotas
3. **Use Proxy Rotation**: For high-volume applications, consider rotating proxies
4. **Handle Errors Gracefully**: Implement proper error handling for API failures
5. **Monitor Usage**: Keep track of API usage to avoid exceeding quotas
