# Best Practices for Code Quality & Performance Improvements

This document provides actionable best practices to improve the Social Flood API's code quality, performance, and maintainability.

---

## 📊 Quick Wins (Implement First)

### 1. **Add Response Compression**
**Impact:** 🚀 High | **Effort:** ⚡ Low

Enable gzip/brotli compression for API responses to reduce bandwidth by 60-80%.

```python
# Add to main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Benefits:**
- Faster response times
- Reduced bandwidth costs
- Better mobile performance

---

### 2. **Implement Database Connection Pooling**
**Impact:** 🚀 High | **Effort:** ⚡ Medium

Use SQLAlchemy with async connection pooling for better database performance.

```python
# Update requirements.txt
asyncpg>=0.30.0  # Async PostgreSQL driver
sqlalchemy[asyncio]>=2.0.0

# Create async database engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Max connections
    max_overflow=10,       # Extra connections if needed
    pool_pre_ping=True,    # Verify connections before use
    pool_recycle=3600,     # Recycle connections after 1 hour
    echo=False             # Set True for SQL logging
)
```

**Benefits:**
- 3-5x faster database queries
- Better resource utilization
- Handle more concurrent requests

---

### 3. **Add Request ID Tracking**
**Impact:** 🎯 Medium | **Effort:** ⚡ Low

Track requests across logs for better debugging.

```python
# app/core/middleware.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**Benefits:**
- Easier debugging
- Request tracing across services
- Better log correlation

---

### 4. **Structured Logging with JSON**
**Impact:** 🎯 Medium | **Effort:** ⚡ Low

Switch to JSON logging for better log parsing and analysis.

```python
# requirements.txt
python-json-logger>=2.0.0

# app/core/logging_config.py
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
```

**Benefits:**
- Easy parsing with log aggregators (ELK, Datadog)
- Better searchability
- Structured data for analysis

---

### 5. **Add Database Migrations with Alembic**
**Impact:** 🚀 High | **Effort:** ⚡ Medium

Manage database schema changes systematically.

```bash
# Install Alembic
pip install alembic>=1.13.0

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

**Benefits:**
- Version-controlled schema changes
- Rollback capability
- Consistent deployments

---

## 🚀 Performance Optimizations

### 6. **Implement Response Caching Headers**
**Impact:** 🚀 High | **Effort:** ⚡ Low

Add proper cache headers for API responses.

```python
from fastapi import Response

@router.get("/trends")
async def get_trends(response: Response):
    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
    response.headers["ETag"] = generate_etag(data)

    return data
```

---

### 7. **Add Database Query Optimization**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

**Add indexes to frequently queried columns:**

```sql
-- Create indexes
CREATE INDEX idx_news_published ON news_articles(published_date DESC);
CREATE INDEX idx_trends_country ON trends(country, date);
CREATE INDEX idx_api_keys_active ON api_keys(key) WHERE active = true;
```

**Use query optimization techniques:**

```python
# Use select_related for foreign keys
articles = await db.execute(
    select(Article)
    .options(selectinload(Article.author))  # Eager loading
    .limit(100)
)

# Use query result caching
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_trending_topics(country: str):
    # Expensive query cached in memory
    pass
```

---

### 8. **Implement Pagination for All List Endpoints**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

Add cursor-based or offset-based pagination.

```python
# app/core/pagination.py
from fastapi import Query
from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar('T')

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int

async def paginate(
    query,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100)
) -> Page[T]:
    total = await db.scalar(select(func.count()).select_from(query))
    items = await db.execute(
        query.offset((page - 1) * size).limit(size)
    )

    return Page(
        items=items.scalars().all(),
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )
```

---

### 9. **Add HTTP/2 Support**
**Impact:** 🎯 Medium | **Effort:** ⚡ Low

Enable HTTP/2 in production for better performance.

```bash
# Update uvicorn command
uvicorn main:app --host 0.0.0.0 --port 8000 --http h11 --loop uvloop
```

Or use hypercorn for native HTTP/2:

```bash
pip install hypercorn[uvloop]>=0.16.0
hypercorn main:app --bind 0.0.0.0:8000 --worker-class uvloop
```

---

### 10. **Optimize Redis Usage**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

Use Redis connection pooling and optimize cache patterns.

```python
# app/core/redis_config.py
import aioredis

redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    max_connections=50,
    decode_responses=True
)

redis_client = aioredis.Redis(connection_pool=redis_pool)

# Use pipeline for multiple operations
async def cache_multiple(items: dict):
    pipe = redis_client.pipeline()
    for key, value in items.items():
        pipe.setex(key, 3600, value)
    await pipe.execute()
```

---

## 🏗️ Code Quality Improvements

### 11. **Achieve 100% Type Hint Coverage**
**Impact:** 🎯 Medium | **Effort:** 🔨 High

Add type hints to all functions and use strict mypy.

```python
# Before
def process_data(data):
    return data.upper()

# After
def process_data(data: str) -> str:
    return data.upper()

# Use Protocol for duck typing
from typing import Protocol

class Cacheable(Protocol):
    def to_cache(self) -> dict: ...

def cache_item(item: Cacheable) -> None:
    redis.set(item.id, item.to_cache())
```

---

### 12. **Implement Dependency Injection**
**Impact:** 🎯 Medium | **Effort:** 🔨 Medium

Use FastAPI's dependency injection for better testability.

```python
# app/core/dependencies.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Use in routes
@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    return await db.execute(select(Item))
```

---

### 13. **Add Repository Pattern**
**Impact:** 🎯 Medium | **Effort:** 🔨 High

Separate data access logic from business logic.

```python
# app/repositories/news_repository.py
from typing import List, Optional

class NewsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, article_id: int) -> Optional[NewsArticle]:
        result = await self.db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalar_one_or_none()

    async def search(self, query: str, limit: int = 10) -> List[NewsArticle]:
        result = await self.db.execute(
            select(NewsArticle)
            .where(NewsArticle.content.contains(query))
            .limit(limit)
        )
        return result.scalars().all()

# Use in services
class NewsService:
    def __init__(self, repo: NewsRepository):
        self.repo = repo

    async def get_trending(self, country: str) -> List[NewsArticle]:
        articles = await self.repo.search(f"trending in {country}")
        return self.process_articles(articles)
```

---

### 14. **Add Proper Error Handling**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

Create custom exception hierarchy and handlers.

```python
# app/core/exceptions.py
class SocialFloodException(Exception):
    """Base exception for all app errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code

class ResourceNotFoundError(SocialFloodException):
    def __init__(self, resource: str, id: str):
        super().__init__(
            f"{resource} with id {id} not found",
            status_code=404
        )

class RateLimitError(SocialFloodException):
    def __init__(self, retry_after: int):
        super().__init__(
            "Rate limit exceeded",
            status_code=429
        )
        self.retry_after = retry_after

# Global exception handler
@app.exception_handler(SocialFloodException)
async def social_flood_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

---

## 📡 Observability & Monitoring

### 15. **Add OpenTelemetry Tracing**
**Impact:** 🚀 High | **Effort:** 🔨 High

Implement distributed tracing for performance insights.

```python
# requirements.txt
opentelemetry-api>=1.23.0
opentelemetry-sdk>=1.23.0
opentelemetry-instrumentation-fastapi>=0.44b0
opentelemetry-exporter-jaeger>=1.23.0

# app/core/tracing.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

# Use in code
tracer = trace.get_tracer(__name__)

async def fetch_data():
    with tracer.start_as_current_span("fetch_data"):
        # Your code here
        pass
```

---

### 16. **Add Application Performance Monitoring (APM)**
**Impact:** 🚀 High | **Effort:** ⚡ Low

Integrate with Sentry for error tracking and performance monitoring.

```python
# requirements.txt
sentry-sdk[fastapi]>=1.40.0

# main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    environment=settings.ENVIRONMENT,
    traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
    profiles_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
    integrations=[FastApiIntegration()],
)
```

---

### 17. **Add Custom Metrics**
**Impact:** 🎯 Medium | **Effort:** 🔨 Medium

Track business metrics beyond basic Prometheus metrics.

```python
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics
api_requests = Counter(
    'api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

response_time = Histogram(
    'api_response_time_seconds',
    'API response time',
    ['endpoint']
)

active_users = Gauge(
    'active_users_total',
    'Number of active users'
)

# Use in middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    api_requests.labels(
        endpoint=request.url.path,
        method=request.method,
        status=response.status_code
    ).inc()

    response_time.labels(endpoint=request.url.path).observe(duration)

    return response
```

---

## 🔒 Security Enhancements

### 18. **Implement OAuth2 with JWT**
**Impact:** 🚀 High | **Effort:** 🔨 High

Add proper authentication with JWT tokens.

```python
# requirements.txt
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# app/core/security.py
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user(user_id)
    if user is None:
        raise credentials_exception
    return user
```

---

### 19. **Add Request Rate Limiting per User**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

Implement per-user rate limiting instead of global.

```python
# app/core/rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# Use user ID instead of IP
def get_user_id(request: Request):
    return request.state.user.id if hasattr(request.state, 'user') else get_remote_address(request)

limiter = Limiter(key_func=get_user_id)

# Different limits for different endpoints
@router.get("/expensive-operation")
@limiter.limit("10/hour")  # 10 requests per hour
async def expensive_operation(request: Request):
    pass

@router.get("/cheap-operation")
@limiter.limit("1000/hour")  # 1000 requests per hour
async def cheap_operation(request: Request):
    pass
```

---

### 20. **Add Input Validation Schemas**
**Impact:** 🚀 High | **Effort:** 🔨 Medium

Use Pydantic for comprehensive input validation.

```python
from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List
from datetime import datetime

class NewsSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    country: str = Field("US", regex="^[A-Z]{2}$", description="Two-letter country code")
    language: str = Field("en", regex="^[a-z]{2}$", description="Two-letter language code")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    from_date: Optional[datetime] = Field(None, description="Start date for results")
    to_date: Optional[datetime] = Field(None, description="End date for results")

    @validator('to_date')
    def validate_date_range(cls, v, values):
        if v and 'from_date' in values and values['from_date']:
            if v < values['from_date']:
                raise ValueError('to_date must be after from_date')
        return v

    @validator('query')
    def sanitize_query(cls, v):
        # Remove SQL injection attempts
        forbidden = ["';", "--", "/*", "*/", "xp_", "DROP", "DELETE"]
        if any(x in v.upper() for x in forbidden):
            raise ValueError('Invalid query string')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "query": "artificial intelligence",
                "country": "US",
                "language": "en",
                "max_results": 10
            }
        }
```

---

## 🧪 Testing Improvements

### 21. **Add Integration Tests**
**Impact:** 🚀 High | **Effort:** 🔨 High

Create comprehensive integration tests.

```python
# tests/integration/test_news_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_news_search_full_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test full flow
        response = await client.get(
            "/api/v1/google-news/search",
            params={"q": "python", "max_results": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 5

        # Test caching
        response2 = await client.get(
            "/api/v1/google-news/search",
            params={"q": "python", "max_results": 5}
        )

        # Should be cached
        assert response2.headers.get("X-Cache") == "HIT"
```

---

### 22. **Add Load Testing**
**Impact:** 🎯 Medium | **Effort:** 🔨 Medium

Use k6 or Locust for load testing.

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class SocialFloodUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def search_news(self):
        self.client.get(
            "/api/v1/google-news/search",
            params={"q": "technology", "max_results": 10},
            headers={"x-api-key": "test-key"}
        )

    @task(1)
    def get_trends(self):
        self.client.get(
            "/api/v1/google-trends/trending",
            params={"country": "US"},
            headers={"x-api-key": "test-key"}
        )

# Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
```

---

### 23. **Add Contract Testing**
**Impact:** 🎯 Medium | **Effort:** 🔨 Medium

Ensure API contracts don't break.

```python
# tests/contract/test_api_contract.py
import pytest
from pact import Consumer, Provider

pact = Consumer('API Client').has_pact_with(Provider('Social Flood API'))

def test_news_search_contract():
    (pact
     .given('news data exists')
     .upon_receiving('a request for news')
     .with_request('GET', '/api/v1/google-news/search', query={'q': 'test'})
     .will_respond_with(200, body={
         'status': 'success',
         'results': [{'title': 'Test News'}]
     }))

    with pact:
        # Make actual request and verify
        response = client.get('/api/v1/google-news/search?q=test')
        assert response.status_code == 200
```

---

## 📚 Documentation Improvements

### 24. **Add Architecture Decision Records (ADRs)**
**Impact:** 🎯 Medium | **Effort:** ⚡ Low

Document important architectural decisions.

```markdown
# ADR-001: Use FastAPI Instead of Flask

## Status
Accepted

## Context
We need a modern Python web framework for our API.

## Decision
Use FastAPI because:
- Native async/await support
- Automatic OpenAPI documentation
- Built-in validation with Pydantic
- High performance (comparable to Node.js and Go)

## Consequences
- Requires Python 3.11+
- Team needs to learn async programming
- Better performance and developer experience
```

---

### 25. **Add Runbooks**
**Impact:** 🎯 Medium | **Effort:** ⚡ Low

Create operational runbooks for common issues.

```markdown
# Runbook: High API Latency

## Symptoms
- API response time > 2 seconds
- Increased error rate
- User complaints

## Diagnosis Steps
1. Check Prometheus metrics: `api_response_time_seconds`
2. Check database connection pool: `db_pool_size`
3. Check Redis connection: `redis_client.ping()`
4. Review slow query log

## Resolution
1. Scale up application servers
2. Add database read replicas
3. Increase Redis memory
4. Enable query caching

## Prevention
- Set up alerts for p95 latency > 1s
- Regular load testing
- Query optimization reviews
```

---

## 🎯 Priority Matrix

| Priority | Impact | Effort | Recommendation |
|----------|--------|--------|----------------|
| **P0** | 🚀 High | ⚡ Low | Implement immediately |
| **P1** | 🚀 High | 🔨 Medium | Implement within 1 sprint |
| **P2** | 🎯 Medium | ⚡ Low | Quick wins, do soon |
| **P3** | 🎯 Medium | 🔨 Medium-High | Plan for future sprints |

### Recommendations by Priority:

**P0 (This Week):**
1. Add response compression
2. Add request ID tracking
3. Implement database connection pooling
4. Add pagination to list endpoints

**P1 (Next 2 Weeks):**
5. Add database migrations (Alembic)
6. Implement structured logging
7. Add proper error handling
8. Optimize Redis usage
9. Add database indexes

**P2 (Next Month):**
10. Add OpenTelemetry tracing
11. Implement APM (Sentry)
12. Add OAuth2/JWT authentication
13. Implement repository pattern
14. Add integration tests

**P3 (Next Quarter):**
15. Add load testing
16. Implement GraphQL support
17. Add contract testing
18. Create ADRs
19. Implement feature flags
20. Add blue-green deployment

---

## 📊 Expected Performance Improvements

| Optimization | Expected Improvement |
|--------------|---------------------|
| Response compression | 60-80% bandwidth reduction |
| Database connection pooling | 3-5x faster queries |
| Redis optimization | 2-3x faster cache operations |
| Pagination | 10-20x faster for large datasets |
| HTTP/2 | 20-30% faster page loads |
| Database indexes | 10-100x faster queries |
| Async database driver | 2-3x throughput increase |

---

## 🎓 Learning Resources

- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Twelve-Factor App](https://12factor.net/)
- [Database Indexing Guide](https://use-the-index-luke.com/)
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [Async Python Patterns](https://docs.python.org/3/library/asyncio.html)

---

**Last Updated:** 2025-11-06
**Version:** 1.6.0
