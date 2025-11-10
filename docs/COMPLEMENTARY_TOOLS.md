# Complementary Open Source Projects for Social Flood API

**Based on Current Tech Stack Analysis**
**Generated:** 2025-11-10
**Stack Version:** Python 3.13 + FastAPI 0.121.0

This document recommends open source projects that complement your **existing technology stack** found in `requirements.txt`.

---

## 📊 Current Stack Analysis

### Core Framework
- ✅ **FastAPI** 0.121.0+ - Modern async web framework
- ✅ **Uvicorn** 0.38.0+ - ASGI server
- ✅ **Pydantic** 2.12.0+ - Data validation

### Data Layer
- ✅ **PostgreSQL** with asyncpg - Primary database
- ✅ **SQLAlchemy** 2.0+ (async) - ORM
- ✅ **Alembic** - Database migrations
- ✅ **Redis** 5.2.0+ - Caching
- ✅ **Qdrant** - Vector database

### Processing & Tasks
- ✅ **Celery** 5.4.0+ - Background tasks
- ✅ **Pandas** 2.2.0+ - Data processing
- ✅ **NLTK** 3.9.1+ - Natural language processing

### Monitoring & Observability
- ✅ **Prometheus** - Metrics
- ✅ **Sentry** - Error tracking
- ✅ **OpenTelemetry** - Distributed tracing

### External APIs
- ✅ **Google Trends** (trendspy)
- ✅ **Google News** (gnews)
- ✅ **YouTube Transcripts**
- ✅ **Newspaper4k** - Article extraction

---

## 🚀 Recommended Complementary Projects

### 1. Message Queue / Event Streaming

#### **RabbitMQ** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/rabbitmq/rabbitmq-server
**Stars:** 12K+ | **License:** MPL 2.0

**Why it complements your stack:**
- Perfect companion to **Celery** (you're already using it)
- More reliable than Redis as a Celery broker
- Better message durability and delivery guarantees
- Native support for task queues, priority queues, and delayed tasks

**Integration:**
```python
# celeryconfig.py
broker_url = 'amqp://guest:guest@localhost:5672//'
result_backend = 'redis://localhost:6379/0'

# Use RabbitMQ as broker, Redis for results
# Best of both worlds for Celery tasks
```

**Use Cases:**
- Celery message broker (better than Redis for production)
- Reliable task queue for background jobs
- Event-driven architecture for real-time updates
- Dead letter queues for failed tasks

**Priority:** 🚀 **P0 - Very High** (Already using Celery, RabbitMQ is the best broker)

**Docker Setup:**
```yaml
# docker-compose.yml
rabbitmq:
  image: rabbitmq:3.13-management-alpine
  ports:
    - "5672:5672"
    - "15672:15672"  # Management UI
  environment:
    - RABBITMQ_DEFAULT_USER=user
    - RABBITMQ_DEFAULT_PASS=password
  healthcheck:
    test: rabbitmq-diagnostics -q ping
    interval: 30s
```

---

#### **Apache Kafka** ⭐⭐⭐⭐
**GitHub:** https://github.com/apache/kafka
**Stars:** 28K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Event streaming for real-time social media data
- Perfect for high-throughput data pipelines
- Works alongside your **Redis** and **PostgreSQL**
- Ideal for time-series social media analytics

**Integration:**
```python
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# Producer
producer = AIOKafkaProducer(bootstrap_servers='localhost:9092')
await producer.start()
await producer.send('social-trends', b'{"keyword": "python", "volume": 1000}')

# Consumer
consumer = AIOKafkaConsumer(
    'social-trends',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest'
)
async for msg in consumer:
    # Process real-time social media data
    process_trend(msg.value)
```

**Use Cases:**
- Real-time trend detection pipeline
- Social media event streaming
- Click-stream analytics for API usage
- Audit logs and activity streams

**Priority:** 🎯 **P1 - High** (Great for real-time analytics)

---

### 2. Search & Indexing

#### **Elasticsearch** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/elastic/elasticsearch
**Stars:** 69K+ | **License:** SSPL/Elastic License

**Why it complements your stack:**
- Full-text search for news articles (you're using gnews/newspaper4k)
- Search across YouTube transcripts
- Complements **PostgreSQL** for complex queries
- Better than SQL for fuzzy search and relevance

**Integration:**
```python
from elasticsearch import AsyncElasticsearch

es = AsyncElasticsearch(['http://localhost:9200'])

# Index news articles
await es.index(
    index='news-articles',
    document={
        'title': article['title'],
        'content': article['text'],
        'published_date': article['date'],
        'source': article['source'],
        'keywords': extract_keywords(article['text'])  # Using your NLTK
    }
)

# Search with NLP-extracted keywords
results = await es.search(
    index='news-articles',
    query={
        'multi_match': {
            'query': search_term,
            'fields': ['title^2', 'content', 'keywords'],
            'fuzziness': 'AUTO'
        }
    }
)
```

**Use Cases:**
- Full-text search across news articles
- YouTube transcript search
- Trend keyword search
- Autocomplete suggestions (complement Google Autocomplete API)
- Article similarity search

**Priority:** 🚀 **P0 - Very High** (Essential for content search)

**Alternative:** **Meilisearch** (lighter, easier to deploy, typo-tolerant)

---

#### **Meilisearch** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/meilisearch/meilisearch
**Stars:** 46K+ | **License:** MIT

**Why it complements your stack:**
- Easier to deploy than Elasticsearch
- Perfect for **FastAPI** integration (built with Rust, super fast)
- Typo-tolerant search for user queries
- Great for autocomplete features

**Integration:**
```python
import meilisearch_python_async as meilisearch

client = meilisearch.Client('http://localhost:7700', 'masterKey')

# Index YouTube transcripts
index = client.index('youtube-transcripts')
await index.add_documents([
    {
        'id': video_id,
        'video_id': video_id,
        'title': transcript['title'],
        'transcript_text': ' '.join([t['text'] for t in transcript['transcript']]),
        'language': transcript['language']
    }
])

# Search with typo tolerance
results = await index.search('pythn tutoral')  # Finds "python tutorial"
```

**Priority:** 🚀 **P0 - Very High** (Easier than Elasticsearch, great for MVP)

---

### 3. Time-Series Database

#### **TimescaleDB** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/timescale/timescaledb
**Stars:** 17K+ | **License:** Apache 2.0

**Why it complements your stack:**
- **PostgreSQL extension** - works with your existing asyncpg/SQLAlchemy
- Purpose-built for time-series data (perfect for trends!)
- Automatic partitioning and compression
- Use same connection pool, migrations (Alembic), and queries

**Integration:**
```sql
-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert existing table to hypertable
SELECT create_hypertable('google_trends_data', 'timestamp');

-- Your existing SQLAlchemy models work as-is!
```

```python
# models.py - Works with your existing SQLAlchemy setup
class TrendData(Base):
    __tablename__ = 'google_trends_data'

    timestamp = Column(DateTime, primary_key=True)
    keyword = Column(String, primary_key=True)
    search_volume = Column(Integer)
    region = Column(String)

# Automatic time-based partitioning and compression
# Query performance 10-100x better for time-series queries
```

**Use Cases:**
- Store Google Trends time-series data
- Social media metrics over time
- API usage analytics
- YouTube view count tracking
- Trend detection algorithms

**Priority:** 🚀 **P0 - Very High** (Perfect fit for your use case + existing PostgreSQL)

---

#### **InfluxDB** ⭐⭐⭐⭐
**GitHub:** https://github.com/influxdata/influxdb
**Stars:** 28K+ | **License:** MIT

**Why it complements your stack:**
- Purpose-built time-series database
- Great for real-time metrics alongside **Prometheus**
- Better retention policies than PostgreSQL
- Native downsampling and aggregation

**Priority:** 🎯 **P1 - High** (If TimescaleDB isn't enough)

---

### 4. Task Queue Monitoring

#### **Flower** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/mher/flower
**Stars:** 6K+ | **License:** BSD-3-Clause

**Why it complements your stack:**
- **Real-time monitoring for Celery** (you're already using it)
- Web-based UI for task management
- Works with your existing Celery setup
- No additional infrastructure needed

**Integration:**
```bash
# Install
pip install flower

# Run (monitors your existing Celery workers)
celery -A your_app flower --port=5555
```

**Features:**
- Monitor Celery tasks in real-time
- View task history and results
- Worker management (restart, shutdown)
- Task rate limiting and throttling
- Integrates with your Prometheus metrics

**Use Cases:**
- Monitor background scraping tasks
- Debug failed news article fetches
- Track YouTube transcript processing
- Monitor Google Trends API calls

**Priority:** 🚀 **P0 - Very High** (Essential if using Celery in production)

---

### 5. API Gateway

#### **Kong** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/Kong/kong
**Stars:** 39K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Sits in front of your **FastAPI** application
- Works with your existing **Prometheus** metrics
- Enhances your **slowapi** rate limiting
- Built on OpenResty (Nginx + Lua)

**Integration:**
```yaml
# kong.yml
services:
  - name: social-flood-api
    url: http://fastapi-app:8000
    routes:
      - name: api-route
        paths:
          - /api/v1
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          hour: 1000
      - name: prometheus
      - name: jwt
      - name: cors
      - name: request-transformer
```

**Use Cases:**
- Centralized rate limiting across multiple API instances
- API key management (complement your existing auth)
- Request/response transformation
- Load balancing across multiple FastAPI workers
- API versioning

**Priority:** 🎯 **P1 - High** (Important for production API)

---

### 6. Workflow Orchestration

#### **Apache Airflow** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/apache/airflow
**Stars:** 36K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Orchestrate complex data pipelines
- Works alongside **Celery** (Airflow can use Celery executor)
- Schedule periodic scraping tasks
- Better than cron for complex workflows

**Integration:**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Daily trend aggregation pipeline
dag = DAG(
    'google_trends_pipeline',
    default_args={
        'owner': 'social-flood',
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
    },
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
)

def fetch_trends():
    # Use your existing trendspy code
    from your_app.services import fetch_google_trends
    trends = fetch_google_trends(keywords=['python', 'javascript'])
    return trends

def process_trends(trends):
    # Use your existing pandas code
    import pandas as pd
    df = pd.DataFrame(trends)
    df.to_sql('trends', engine, if_exists='append')

fetch_task = PythonOperator(
    task_id='fetch_google_trends',
    python_callable=fetch_trends,
    dag=dag,
)

process_task = PythonOperator(
    task_id='process_trends',
    python_callable=process_trends,
    dag=dag,
)

fetch_task >> process_task
```

**Use Cases:**
- Daily Google Trends data collection
- Periodic news article scraping
- YouTube channel monitoring
- Data warehouse ETL pipelines
- Report generation

**Priority:** 🚀 **P0 - Very High** (Essential for production data pipelines)

---

#### **Prefect** ⭐⭐⭐⭐
**GitHub:** https://github.com/PrefectHQ/prefect
**Stars:** 16K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Modern alternative to Airflow
- Better Python-native experience
- Works with your existing **async** code
- Easier deployment than Airflow

**Priority:** 🎯 **P1 - High** (If you prefer modern Python over Airflow)

---

### 7. Vector Search Enhancement

#### **Weaviate** ⭐⭐⭐⭐
**GitHub:** https://github.com/weaviate/weaviate
**Stars:** 11K+ | **License:** BSD-3-Clause

**Why it complements your stack:**
- Complements your **Qdrant** vector database
- GraphQL API (nice complement to REST)
- Better for hybrid search (vector + keyword)
- Built-in NLP models

**Integration:**
```python
import weaviate

client = weaviate.Client("http://localhost:8080")

# Store news articles with embeddings
client.data_object.create(
    {
        "title": article['title'],
        "content": article['text'],
        "published_date": article['date'],
    },
    "NewsArticle",
    vector=embedding  # From your NLP pipeline
)

# Semantic search
results = client.query.get(
    "NewsArticle", ["title", "content"]
).with_near_text({
    "concepts": ["artificial intelligence ethics"]
}).with_limit(10).do()
```

**Priority:** 📈 **P2 - Medium** (You already have Qdrant)

---

### 8. NLP Enhancement

#### **Hugging Face Transformers** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/huggingface/transformers
**Stars:** 130K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Enhances your **NLTK** capabilities
- State-of-the-art sentiment analysis
- Works with your existing **newspaper4k** articles
- Better than NLTK for modern NLP tasks

**Integration:**
```python
from transformers import pipeline

# Sentiment analysis for news articles
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)

# Process articles from your newspaper4k extraction
article_text = newspaper_article.text
sentiment = sentiment_analyzer(article_text[:512])[0]
# {'label': 'POSITIVE', 'score': 0.9998}

# Summarization for long articles
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
summary = summarizer(article_text, max_length=150, min_length=40)[0]

# Named Entity Recognition
ner = pipeline("ner", model="dslim/bert-base-NER")
entities = ner(article_text)
# Extract companies, people, locations from news
```

**Use Cases:**
- Advanced sentiment analysis for news articles
- Article summarization for YouTube transcripts
- Named entity extraction from news
- Multi-language content analysis

**Priority:** 🚀 **P0 - Very High** (Massive upgrade over NLTK)

---

#### **spaCy** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/explosion/spaCy
**Stars:** 29K+ | **License:** MIT

**Why it complements your stack:**
- Production-ready NLP (unlike NLTK)
- Works with your **newspaper4k** pipeline
- Faster than Transformers for basic NLP
- Better tokenization than NLTK

**Integration:**
```python
import spacy

nlp = spacy.load("en_core_web_sm")

# Process news article
doc = nlp(newspaper_article.text)

# Extract keywords automatically
keywords = [chunk.text for chunk in doc.noun_chunks]

# Named entity recognition
entities = {
    'organizations': [ent.text for ent in doc.ents if ent.label_ == 'ORG'],
    'people': [ent.text for ent in doc.ents if ent.label_ == 'PERSON'],
    'locations': [ent.text for ent in doc.ents if ent.label_ == 'GPE'],
    'money': [ent.text for ent in doc.ents if ent.label_ == 'MONEY'],
}

# Better than NLTK for production use
```

**Priority:** 🚀 **P0 - Very High** (Replace NLTK for production)

---

### 9. Analytics Database

#### **ClickHouse** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/ClickHouse/ClickHouse
**Stars:** 36K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Column-oriented database for analytics
- Complements **PostgreSQL** (OLTP) with OLAP
- 100-1000x faster than PostgreSQL for analytics
- Perfect for **Pandas** data analysis

**Integration:**
```python
from clickhouse_driver import Client

client = Client('localhost')

# Store Google Trends data for fast analytics
client.execute('''
    CREATE TABLE IF NOT EXISTS trends (
        date Date,
        keyword String,
        search_volume UInt32,
        region String,
        category String
    ) ENGINE = MergeTree()
    ORDER BY (date, keyword)
''')

# Insert from your Pandas DataFrame
df = pd.DataFrame(trends_data)
client.insert_dataframe('INSERT INTO trends VALUES', df)

# Lightning-fast aggregations
result = client.execute('''
    SELECT
        keyword,
        AVG(search_volume) as avg_volume,
        quantile(0.95)(search_volume) as p95_volume
    FROM trends
    WHERE date >= today() - INTERVAL 30 DAY
    GROUP BY keyword
    ORDER BY avg_volume DESC
    LIMIT 100
''')
```

**Use Cases:**
- Real-time trend analytics
- Historical trend analysis
- User behavior analytics
- API usage statistics
- Social media metrics aggregation

**Priority:** 🚀 **P0 - Very High** (Perfect for your analytics use case)

---

### 10. Monitoring Enhancement

#### **Grafana** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/grafana/grafana
**Stars:** 62K+ | **License:** AGPL-3.0

**Why it complements your stack:**
- Visualize your **Prometheus** metrics
- Monitor **PostgreSQL**, **Redis**, **Celery**
- Works with your **Sentry** error data
- Integrates with **OpenTelemetry** traces

**Integration:**
```yaml
# docker-compose.yml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    - ./grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
```

**Pre-built Dashboards:**
- FastAPI application metrics
- PostgreSQL performance
- Redis cache hit rates
- Celery task queues
- API response times
- Error rates from Sentry

**Priority:** 🚀 **P0 - Very High** (Essential with Prometheus)

---

#### **Jaeger** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/jaegertracing/jaeger
**Stars:** 20K+ | **License:** Apache 2.0

**Why it complements your stack:**
- Visualize your **OpenTelemetry** traces
- See end-to-end request flow
- Debug slow API calls
- Compatible with your existing OTLP exporter

**Integration:**
```python
# You're already using OpenTelemetry, just add Jaeger exporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

# Traces automatically sent to Jaeger UI
# View at http://localhost:16686
```

**Priority:** 🚀 **P0 - Very High** (Essential with OpenTelemetry)

---

### 11. Documentation

#### **Redoc** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/Redocly/redoc
**Stars:** 23K+ | **License:** MIT

**Why it complements your stack:**
- Better API docs than FastAPI's default Swagger UI
- Three-panel layout (nav, docs, examples)
- Works with your existing OpenAPI schema
- One-line integration with FastAPI

**Integration:**
```python
from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html

app = FastAPI()

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js",
    )
```

**Priority:** 🎯 **P1 - High** (Professional API documentation)

---

### 12. Load Testing

#### **Locust** ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/locustio/locust
**Stars:** 24K+ | **License:** MIT

**Why it complements your stack:**
- Python-based (same language as your app)
- Test your **FastAPI** endpoints
- Works with **Prometheus** for metrics
- Async support for testing async APIs

**Integration:**
```python
from locust import HttpUser, task, between

class SocialFloodUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_google_trends(self):
        self.client.get(
            "/api/v1/google-trends/interest-over-time",
            params={"keywords": "python", "timeframe": "today 3-m"},
            headers={"X-API-Key": "test-key"}
        )

    @task(2)
    def get_news(self):
        self.client.get(
            "/api/v1/news/top/",
            params={"language": "en", "country": "US"},
            headers={"X-API-Key": "test-key"}
        )

    @task(1)
    def get_youtube_transcript(self):
        self.client.get(
            "/api/v1/youtube-transcripts/get-transcript",
            params={"video_id": "dQw4w9WgXcQ"},
            headers={"X-API-Key": "test-key"}
        )
```

**Priority:** 🚀 **P0 - Very High** (Essential for production readiness)

---

### 13. Caching Layer

#### **KeyDB** ⭐⭐⭐⭐
**GitHub:** https://github.com/Snapchat/KeyDB
**Stars:** 11K+ | **License:** BSD-3-Clause

**Why it complements your stack:**
- Drop-in replacement for **Redis**
- Multi-threaded (faster than Redis)
- Same API as Redis (works with your redis>=5.2.0)
- Better performance for high-traffic APIs

**Integration:**
```python
# No code changes needed!
# Just change Redis connection string to KeyDB
# Or use in docker-compose.yml:

keydb:
  image: eqalpha/keydb:latest
  ports:
    - "6379:6379"
  command: keydb-server --server-threads 4
```

**Priority:** 📈 **P2 - Medium** (Optimization, Redis is fine for now)

---

### 14. API Client SDK Generator

#### **FastAPI Code Generator** ⭐⭐⭐⭐
**GitHub:** https://github.com/koxudaxi/fastapi-code-generator
**Stars:** 1K+ | **License:** MIT

**Why it complements your stack:**
- Auto-generate Python/TypeScript clients for your API
- Uses your existing **Pydantic** models
- Creates typed clients from OpenAPI schema
- Perfect for API consumers

**Integration:**
```bash
# Generate Python client from your OpenAPI schema
fastapi-codegen \
  --url http://localhost:8000/openapi.json \
  --output ./sdk/python

# Now users can use your API with type hints
from social_flood_client import SocialFloodClient

client = SocialFloodClient(api_key="your-key")
trends = await client.get_google_trends(keywords=["python"])
```

**Priority:** 🎯 **P1 - High** (Great for API adoption)

---

## 📊 Priority Matrix

### 🚀 P0 - Must Have (Deploy First)

| Project | Category | Why Critical |
|---------|----------|--------------|
| **RabbitMQ** | Message Queue | Essential Celery broker for production |
| **Flower** | Monitoring | Monitor Celery tasks in real-time |
| **TimescaleDB** | Database | Perfect for time-series trends data |
| **Elasticsearch/Meilisearch** | Search | Essential for content search |
| **Hugging Face Transformers** | NLP | Modern sentiment analysis |
| **spaCy** | NLP | Production-ready NLP (replace NLTK) |
| **ClickHouse** | Analytics | Fast analytics for trends data |
| **Grafana** | Monitoring | Visualize Prometheus metrics |
| **Jaeger** | Monitoring | Visualize OpenTelemetry traces |
| **Apache Airflow** | Orchestration | Schedule data pipelines |
| **Locust** | Testing | Load test before production |

### 🎯 P1 - Should Have (Deploy Soon)

| Project | Category | Why Important |
|---------|----------|---------------|
| **Apache Kafka** | Streaming | Real-time event processing |
| **Kong** | API Gateway | Production API management |
| **Redoc** | Documentation | Better API docs |
| **FastAPI Code Generator** | SDK | API client generation |
| **Prefect** | Orchestration | Alternative to Airflow |

### 📈 P2 - Nice to Have (Future)

| Project | Category | Why Useful |
|---------|----------|------------|
| **Weaviate** | Vector Search | Hybrid search (you have Qdrant) |
| **KeyDB** | Caching | Faster Redis (optimization) |
| **InfluxDB** | Time-Series | Alternative to TimescaleDB |

---

## 🏗️ Suggested Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Kong API Gateway                         │
│  • Rate Limiting  • Authentication  • Monitoring            │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌─────────┐         ┌─────────┐        ┌─────────┐
    │ FastAPI │         │ FastAPI │        │ FastAPI │
    │ Worker  │         │ Worker  │        │ Worker  │
    └─────────┘         └─────────┘        └─────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐      ┌──────────────┐    ┌──────────┐
    │PostgreSQL│      │ TimescaleDB  │    │  Redis   │
    │  (OLTP)  │      │ (Time-Series)│    │ (Cache)  │
    └──────────┘      └──────────────┘    └──────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │  ClickHouse  │
                      │  (Analytics) │
                      └──────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Message Queue Layer                      │
├─────────────────────────────────────────────────────────────┤
│  RabbitMQ (Celery) ──► Kafka (Events) ──► Elasticsearch    │
└─────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    ┌─────────┐         ┌─────────┐        ┌─────────┐
    │ Celery  │         │ Airflow │        │  NLP    │
    │ Workers │         │  DAGs   │        │Pipeline │
    └─────────┘         └─────────┘        └─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐      ┌──────────────┐    ┌──────────┐
    │Prometheus│      │    Jaeger    │    │  Sentry  │
    │(Metrics) │      │   (Traces)   │    │ (Errors) │
    └──────────┘      └──────────────┘    └──────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                        ┌──────────┐
                        │ Grafana  │
                        │(Dashboards)
                        └──────────┘
```

---

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. **RabbitMQ** - Switch Celery broker from Redis
2. **Flower** - Monitor Celery tasks
3. **Grafana** - Visualize existing Prometheus metrics
4. **Jaeger** - Connect to existing OpenTelemetry

**Impact:** Better task reliability + visibility

---

### Phase 2: Data Layer (Week 3-4)
1. **TimescaleDB** - Enable on existing PostgreSQL
2. **Elasticsearch/Meilisearch** - Index news articles
3. **ClickHouse** - Analytics database
4. **Locust** - Load testing

**Impact:** Better performance + search

---

### Phase 3: NLP Enhancement (Week 5-6)
1. **Hugging Face Transformers** - Advanced sentiment
2. **spaCy** - Replace NLTK
3. **Apache Airflow** - Data pipelines

**Impact:** Better insights + automation

---

### Phase 4: Scaling (Week 7-8)
1. **Kong** - API gateway
2. **Apache Kafka** - Event streaming
3. **Redoc** - Better docs

**Impact:** Production-ready scaling

---

## 💰 Cost Estimation

| Tier | Monthly Cost | Projects Included |
|------|-------------|-------------------|
| **Free Tier** | $0 | All projects (self-hosted) |
| **Small (1 server)** | $40-80/mo | All P0 projects on single server |
| **Medium (3-5 servers)** | $200-400/mo | All P0 + P1 projects |
| **Large (10+ servers)** | $1000+/mo | Full stack with redundancy |

**All projects are open source and can run on-premise at no licensing cost.**

---

## 📚 Quick Start Guide

### 1. Set Up Message Queue
```bash
# docker-compose.yml
rabbitmq:
  image: rabbitmq:3.13-management-alpine
  ports:
    - "5672:5672"
    - "15672:15672"

# Update celeryconfig.py
broker_url = 'amqp://guest:guest@rabbitmq:5672//'
```

### 2. Add Search
```bash
# Meilisearch (easiest)
docker run -d -p 7700:7700 getmeili/meilisearch:latest

# Or Elasticsearch (more features)
docker run -d -p 9200:9200 elasticsearch:8.11.0
```

### 3. Enable TimescaleDB
```sql
-- In your existing PostgreSQL
CREATE EXTENSION IF NOT EXISTS timescaledb;

SELECT create_hypertable('google_trends_data', 'timestamp');
```

### 4. Set Up Monitoring
```bash
# docker-compose.yml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"

jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"
    - "6831:6831/udp"
```

---

## 🔗 Integration Examples

### Complete Stack Integration

```python
# app/main.py
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from elasticsearch import AsyncElasticsearch
import meilisearch_python_async as meilisearch

app = FastAPI()

# Existing: Prometheus
Instrumentator().instrument(app).expose(app)

# Add: Jaeger tracing
tracer = trace.get_tracer(__name__)

# Add: Search
es = AsyncElasticsearch(['http://elasticsearch:9200'])
meili = meilisearch.Client('http://meilisearch:7700')

@app.get("/api/v1/search")
async def search(q: str):
    with tracer.start_as_current_span("search"):
        # Search in Elasticsearch
        results = await es.search(
            index='articles',
            query={'match': {'content': q}}
        )
        return results

# Celery task with RabbitMQ
@celery_app.task
def fetch_trends(keyword: str):
    # Your existing trendspy code
    trends = fetch_google_trends(keyword)

    # Store in TimescaleDB (automatic with SQLAlchemy)
    session.add(TrendData(
        timestamp=datetime.now(),
        keyword=keyword,
        search_volume=trends['volume']
    ))
    session.commit()

    # Send to Kafka for real-time processing
    producer.send('trends-topic', trends)
```

---

## 📖 Additional Resources

### Documentation Links
- RabbitMQ: https://www.rabbitmq.com/documentation.html
- TimescaleDB: https://docs.timescale.com/
- Meilisearch: https://www.meilisearch.com/docs
- Elasticsearch: https://www.elastic.co/guide/
- Hugging Face: https://huggingface.co/docs
- Apache Airflow: https://airflow.apache.org/docs/
- ClickHouse: https://clickhouse.com/docs/
- Grafana: https://grafana.com/docs/
- Jaeger: https://www.jaegertracing.io/docs/

### FastAPI Integration Guides
- https://fastapi.tiangolo.com/advanced/
- https://github.com/tiangolo/full-stack-fastapi-postgresql

---

## 🎯 Next Steps

1. **Deploy RabbitMQ + Flower** (1 day)
   - Immediate improvement in Celery reliability
   - Visibility into background tasks

2. **Add Meilisearch** (1-2 days)
   - Enable full-text search
   - Better user experience

3. **Enable TimescaleDB** (1 day)
   - Better time-series performance
   - No migration needed (PostgreSQL extension)

4. **Set Up Grafana + Jaeger** (1 day)
   - Visualize existing metrics
   - Debug slow requests

5. **Upgrade NLP Stack** (2-3 days)
   - Add Hugging Face Transformers
   - Replace NLTK with spaCy

---

**Generated by:** Social Flood API Analysis
**Based on:** requirements.txt (Python 3.13 + FastAPI 0.121.0)
**Last Updated:** 2025-11-10
