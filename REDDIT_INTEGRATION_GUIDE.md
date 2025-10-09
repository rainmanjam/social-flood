# Reddit Integration Guide

Complete implementation guide for adding Reddit scraping capabilities to Social Flood API.

---

## Table of Contents

1. [Overview](#overview)
2. [Why AsyncPRAW?](#why-asyncpraw)
3. [Setup Instructions](#setup-instructions)
4. [Implementation Files](#implementation-files)
5. [Testing](#testing)
6. [Usage Examples](#usage-examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide provides step-by-step instructions to integrate Reddit API functionality into the Social Flood API using **AsyncPRAW** (Async Python Reddit API Wrapper).

**Features:**
- Subreddit post scraping
- Comment extraction
- Reddit-wide search
- Subreddit information
- Async/await support
- Built-in caching
- Rate limiting compliance

---

## Why AsyncPRAW?

### Comparison of Reddit Scraping Libraries

| Library | Async | Active | Stars | License | Verdict |
|---------|-------|--------|-------|---------|---------|
| **asyncpraw** | ✅ Yes | ✅ Active | 540+ | MIT | ⭐⭐⭐⭐⭐ **RECOMMENDED** |
| praw | ❌ No | ✅ Active | 3.3k+ | BSD | ⭐⭐⭐⭐ Good (but sync) |
| pushshift.io | N/A | ❌ Unstable | N/A | N/A | ⚠️ Service deprecated |
| reddit-api | ❌ No | ❌ Stale | 200+ | MIT | ⚠️ Not maintained |

**AsyncPRAW** is the best choice because:
- ✅ Official async wrapper for Reddit API
- ✅ Actively maintained by Reddit API team
- ✅ Full async/await support (matches our FastAPI architecture)
- ✅ Built-in rate limiting
- ✅ OAuth2 authentication
- ✅ Comprehensive documentation
- ✅ MIT License (fully compatible)

---

## Setup Instructions

### Step 1: Get Reddit API Credentials

1. Go to https://www.reddit.com/prefs/apps
2. Scroll to "Developed Applications"
3. Click **"Create App"** or **"Create Another App"**
4. Fill in the form:
   - **Name:** Social Flood API
   - **App type:** Select **script**
   - **Description:** API for social media data aggregation
   - **About URL:** (leave blank or add your website)
   - **Redirect URI:** http://localhost:8000
5. Click **"Create app"**
6. Copy your credentials:
   - **Client ID:** (appears under app name)
   - **Client Secret:** (appears as "secret")

### Step 2: Install Dependencies

Add to `requirements.txt`:

```txt
asyncpraw>=7.7.0
```

Install:

```bash
pip install asyncpraw
```

### Step 3: Update Configuration

Add Reddit settings to `app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Reddit API settings
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "Social Flood API v1.0"
    REDDIT_USERNAME: Optional[str] = None
    REDDIT_PASSWORD: Optional[str] = None
```

Add to `.env`:

```bash
# Reddit API Configuration
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=Social Flood API v1.0
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
```

Update `.env.example`:

```bash
# Reddit API Configuration
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=Social Flood API v1.0
REDDIT_USERNAME=your_username
REDDIT_PASSWORD=your_password
```

---

## Implementation Files

### File 1: Reddit Service (`app/services/reddit_service.py`)

Create the Reddit service file. See the complete implementation in the main evaluation document under "Reddit Integration" section, or use this starter:

```python
# app/services/reddit_service.py
import asyncpraw
from typing import List, Dict, Optional
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class RedditService:
    """Service for interacting with Reddit API using AsyncPRAW"""
    
    def __init__(self):
        self.reddit = None
    
    async def __aenter__(self):
        """Context manager entry - initialize Reddit client"""
        self.reddit = asyncpraw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close Reddit client"""
        if self.reddit:
            await self.reddit.close()
    
    # Add methods from the full implementation:
    # - get_subreddit_posts()
    # - get_post_comments()
    # - search_posts()
    # - get_subreddit_info()
```

**Full implementation:** See `PROJECT_EVALUATION_AND_RECOMMENDATIONS.md` Section 5.3

### File 2: Reddit API Router (`app/api/reddit/reddit_api.py`)

Create the API router directory and file:

```bash
mkdir -p app/api/reddit
touch app/api/reddit/__init__.py
touch app/api/reddit/reddit_api.py
```

**Full implementation:** See `PROJECT_EVALUATION_AND_RECOMMENDATIONS.md` Section 5.4

### File 3: Register Router

Update your main application file to include the Reddit router.

If you have `app/api/v1/__init__.py` or similar:

```python
# app/api/v1/__init__.py
from fastapi import APIRouter
from app.api.google_news.google_news_api import gnews_router
from app.api.google_trends.google_trends_api import trends_router
from app.api.google_autocomplete.google_autocomplete_api import autocomplete_router
from app.api.youtube_transcripts.youtube_transcripts_api import youtube_router
from app.api.reddit.reddit_api import reddit_router  # NEW

api_router = APIRouter()

# Include all routers
api_router.include_router(gnews_router, prefix="/google-news", tags=["Google News"])
api_router.include_router(trends_router, prefix="/google-trends", tags=["Google Trends"])
api_router.include_router(autocomplete_router, prefix="/google-autocomplete", tags=["Google Autocomplete"])
api_router.include_router(youtube_router, prefix="/youtube-transcripts", tags=["YouTube"])
api_router.include_router(reddit_router, tags=["Reddit"])  # NEW
```

Or in `app/main.py`:

```python
from app.api.reddit.reddit_api import reddit_router

app.include_router(reddit_router, prefix="/api/v1")
```

---

## Testing

### Unit Tests

Create `tests/unit/test_reddit_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.reddit_service import RedditService

@pytest.mark.asyncio
async def test_reddit_service_initialization():
    """Test Reddit service can be initialized"""
    with patch('asyncpraw.Reddit') as mock_reddit:
        async with RedditService() as reddit_service:
            assert reddit_service.reddit is not None
            mock_reddit.assert_called_once()

@pytest.mark.asyncio
async def test_get_subreddit_posts():
    """Test fetching subreddit posts"""
    with patch('asyncpraw.Reddit') as mock_reddit:
        # Setup mock
        mock_subreddit = AsyncMock()
        mock_submission = MagicMock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Post"
        mock_submission.author = "test_user"
        
        # Configure async iterator
        async def mock_hot(*args, **kwargs):
            yield mock_submission
        
        mock_subreddit.hot = mock_hot
        mock_reddit.return_value.subreddit.return_value = mock_subreddit
        
        async with RedditService() as reddit_service:
            posts = await reddit_service.get_subreddit_posts("python", limit=1)
            assert len(posts) > 0
            assert posts[0]["id"] == "test123"
```

### Integration Tests

Create `tests/integration/test_reddit_api.py`:

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_subreddit_posts_endpoint():
    """Test /reddit/subreddit/{name}/posts endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/reddit/subreddit/python/posts",
            params={"limit": 5, "sort": "hot"},
            headers={"x-api-key": "test_api_key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert "subreddit" in data
        assert data["subreddit"] == "python"
        assert isinstance(data["posts"], list)

@pytest.mark.asyncio
async def test_search_reddit_endpoint():
    """Test /reddit/search endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/reddit/search",
            params={"query": "python programming", "limit": 10},
            headers={"x-api-key": "test_api_key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "python programming"

@pytest.mark.asyncio
async def test_get_subreddit_info_endpoint():
    """Test /reddit/subreddit/{name}/info endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/reddit/subreddit/python/info",
            headers={"x-api-key": "test_api_key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "subscribers" in data
```

Run tests:

```bash
pytest tests/integration/test_reddit_api.py -v
```

---

## Usage Examples

### Example 1: Get Hot Posts from a Subreddit

```bash
curl -X GET "http://localhost:8000/api/v1/reddit/subreddit/technology/posts?limit=10&sort=hot" \
  -H "x-api-key: your_api_key"
```

Response:

```json
{
  "subreddit": "technology",
  "sort": "hot",
  "time_filter": "day",
  "count": 10,
  "posts": [
    {
      "id": "abc123",
      "title": "New AI breakthrough announced",
      "author": "tech_enthusiast",
      "created_utc": 1696800000.0,
      "score": 5432,
      "upvote_ratio": 0.95,
      "num_comments": 234,
      "url": "https://example.com/article",
      "permalink": "https://reddit.com/r/technology/comments/abc123/...",
      "selftext": "Article content...",
      "is_self": false,
      "link_flair_text": "Article",
      "over_18": false,
      "spoiler": false,
      "stickied": false
    }
  ]
}
```

### Example 2: Get Top Posts from Last Week

```bash
curl -X GET "http://localhost:8000/api/v1/reddit/subreddit/python/posts?limit=20&sort=top&time_filter=week" \
  -H "x-api-key: your_api_key"
```

### Example 3: Get Comments from a Specific Post

```bash
curl -X GET "http://localhost:8000/api/v1/reddit/post/abc123/comments?limit=50&sort=best" \
  -H "x-api-key: your_api_key"
```

Response:

```json
{
  "submission_id": "abc123",
  "sort": "best",
  "count": 50,
  "comments": [
    {
      "id": "def456",
      "author": "commenter_user",
      "body": "Great article! I learned...",
      "created_utc": 1696800100.0,
      "score": 123,
      "is_submitter": false,
      "stickied": false,
      "depth": 0,
      "permalink": "https://reddit.com/r/technology/comments/abc123/.../def456"
    }
  ]
}
```

### Example 4: Search Reddit

```bash
curl -X GET "http://localhost:8000/api/v1/reddit/search?query=artificial+intelligence&limit=25&sort=relevance" \
  -H "x-api-key: your_api_key"
```

### Example 5: Get Subreddit Information

```bash
curl -X GET "http://localhost:8000/api/v1/reddit/subreddit/MachineLearning/info" \
  -H "x-api-key: your_api_key"
```

Response:

```json
{
  "name": "MachineLearning",
  "title": "Machine Learning",
  "description": "A subreddit dedicated to learning machine learning",
  "subscribers": 2500000,
  "created_utc": 1284439400.0,
  "over18": false,
  "url": "https://reddit.com/r/MachineLearning",
  "icon_img": "https://..."
}
```

### Example 6: Python Client Usage

```python
import httpx
import asyncio

async def get_reddit_posts():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/reddit/subreddit/python/posts",
            params={"limit": 10, "sort": "hot"},
            headers={"x-api-key": "your_api_key"}
        )
        return response.json()

# Run
posts_data = asyncio.run(get_reddit_posts())
print(f"Found {posts_data['count']} posts")
for post in posts_data['posts']:
    print(f"- {post['title']} ({post['score']} points)")
```

---

## Best Practices

### 1. Respect Rate Limits

Reddit API has strict rate limits:
- **60 requests per minute** for authenticated users
- **10 requests per minute** for unauthenticated users

**Best practices:**
- Use caching aggressively (cache TTL: 5-15 minutes for hot content)
- Implement exponential backoff for retries
- Monitor rate limit headers
- Batch requests when possible

### 2. Caching Strategy

```python
# Good caching strategy
CACHE_TTL_BY_ENDPOINT = {
    "subreddit_posts_hot": 300,      # 5 minutes
    "subreddit_posts_top": 900,      # 15 minutes
    "subreddit_info": 3600,          # 1 hour
    "search": 600,                   # 10 minutes
    "comments": 300,                 # 5 minutes
}
```

### 3. Error Handling

```python
from asyncpraw.exceptions import RedditAPIException, ClientException

try:
    async with RedditService() as reddit:
        posts = await reddit.get_subreddit_posts("nonexistent")
except RedditAPIException as e:
    # Handle API errors (rate limits, permissions, etc.)
    logger.error(f"Reddit API error: {e}")
    raise HTTPException(status_code=503, detail="Reddit API unavailable")
except ClientException as e:
    # Handle client errors (network issues, etc.)
    logger.error(f"Reddit client error: {e}")
    raise HTTPException(status_code=500, detail="Failed to connect to Reddit")
```

### 4. Content Filtering

Always filter sensitive content:

```python
def filter_nsfw_posts(posts: List[Dict]) -> List[Dict]:
    """Filter out NSFW content"""
    return [post for post in posts if not post.get("over_18", False)]

def filter_spoilers(posts: List[Dict]) -> List[Dict]:
    """Filter out spoiler posts"""
    return [post for post in posts if not post.get("spoiler", False)]
```

### 5. Pagination

For large result sets:

```python
async def get_all_posts_paginated(subreddit: str, total_limit: int = 100):
    """Get posts with pagination"""
    all_posts = []
    batch_size = 25
    
    for offset in range(0, total_limit, batch_size):
        batch = await reddit_service.get_subreddit_posts(
            subreddit,
            limit=min(batch_size, total_limit - offset)
        )
        all_posts.extend(batch)
        
        if len(batch) < batch_size:
            break  # No more posts available
    
    return all_posts
```

---

## Troubleshooting

### Issue 1: Authentication Failed

**Error:**
```
asyncprawcore.exceptions.OAuthException: invalid_grant error processing request
```

**Solution:**
- Verify credentials in `.env` are correct
- Ensure Reddit account is not banned or suspended
- Check that app type is set to "script" in Reddit settings
- Try regenerating your client secret

### Issue 2: Rate Limit Exceeded

**Error:**
```
asyncprawcore.exceptions.TooManyRequests: received 429 HTTP response
```

**Solution:**
- Implement exponential backoff
- Increase cache TTL
- Reduce request frequency
- Check Redis cache is working

```python
import asyncio
from asyncprawcore.exceptions import TooManyRequests

async def get_with_retry(func, max_retries=3):
    """Retry with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return await func()
        except TooManyRequests:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Rate limited. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
```

### Issue 3: Subreddit Not Found

**Error:**
```
asyncprawcore.exceptions.NotFound: received 404 HTTP response
```

**Solution:**
- Verify subreddit name is correct (case-sensitive)
- Check if subreddit is private or banned
- Use subreddit search first to find valid names

### Issue 4: Private/Quarantined Subreddit

**Error:**
```
asyncprawcore.exceptions.Forbidden: received 403 HTTP response
```

**Solution:**
- Subreddit may be private (requires membership)
- Subreddit may be quarantined (requires opt-in)
- Cannot access via API - return appropriate error to user

```python
from asyncprawcore.exceptions import Forbidden

try:
    posts = await reddit_service.get_subreddit_posts(subreddit_name)
except Forbidden:
    raise HTTPException(
        status_code=403,
        detail=f"Subreddit r/{subreddit_name} is private or restricted"
    )
```

### Issue 5: Slow Response Times

**Symptoms:**
- Requests taking >5 seconds
- Timeouts occurring

**Solutions:**
1. Check cache hit rate:
```python
cache_stats = await cache_manager.get_stats()
logger.info(f"Cache hit rate: {cache_stats['hit_rate']}%")
```

2. Reduce result limits:
```python
# Instead of:
posts = await get_subreddit_posts(limit=100)

# Use:
posts = await get_subreddit_posts(limit=25)
```

3. Enable connection pooling (already implemented in service)

### Issue 6: Memory Leaks

**Symptoms:**
- Memory usage increasing over time
- Application crashes

**Solution:**
Always use context manager:

```python
# CORRECT ✅
async with RedditService() as reddit:
    posts = await reddit.get_subreddit_posts("python")

# INCORRECT ❌ - Will leak connections
reddit = RedditService()
await reddit.__aenter__()
posts = await reddit.get_subreddit_posts("python")
# Missing __aexit__!
```

---

## Performance Benchmarks

Expected performance (with caching):

| Operation | First Request | Cached Request | Cache TTL |
|-----------|---------------|----------------|-----------|
| Get subreddit posts (10) | ~800ms | ~5ms | 5 min |
| Get post comments (50) | ~1200ms | ~8ms | 5 min |
| Search Reddit (25 results) | ~1500ms | ~10ms | 10 min |
| Get subreddit info | ~600ms | ~3ms | 1 hour |

---

## Security Considerations

### 1. Credential Management

- ✅ Store credentials in environment variables
- ✅ Never commit credentials to version control
- ✅ Use secret management systems in production (AWS Secrets Manager, etc.)
- ✅ Rotate credentials regularly

### 2. Content Sanitization

```python
import bleach

def sanitize_reddit_content(text: str) -> str:
    """Sanitize user-generated content"""
    # Remove potentially harmful HTML
    clean_text = bleach.clean(text)
    return clean_text
```

### 3. Rate Limiting

Implement additional API-level rate limiting:

```python
from app.core.rate_limiter import rate_limit

@router.get("/reddit/subreddit/{name}/posts")
@rate_limit(requests=30, window=60)  # 30 requests per minute
async def get_posts(...):
    pass
```

---

## Next Steps

1. ✅ Complete implementation using code from main document
2. ✅ Test all endpoints thoroughly
3. ✅ Add to API documentation (Swagger/ReDoc)
4. ✅ Monitor performance and adjust cache TTLs
5. ✅ Implement additional features:
   - User profile scraping
   - Trending subreddits
   - Sentiment analysis on comments
   - Post/comment aggregation
   - Reddit awards tracking

---

## Additional Resources

- **AsyncPRAW Documentation:** https://asyncpraw.readthedocs.io/
- **Reddit API Documentation:** https://www.reddit.com/dev/api/
- **Reddit API Rules:** https://github.com/reddit-archive/reddit/wiki/API
- **Rate Limit Info:** https://www.reddit.com/wiki/api#wiki_api_rules

---

## Support

For issues or questions:
- Check `PROJECT_EVALUATION_AND_RECOMMENDATIONS.md`
- Review AsyncPRAW documentation
- Check Reddit API status: https://www.redditstatus.com/

---

**Last Updated:** October 8, 2025  
**Version:** 1.0
