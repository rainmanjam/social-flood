# Social Flood API

A powerful API for accessing and aggregating data from various Google services including Google News, Google Trends, Google Autocomplete, and YouTube Transcripts.

## Features

- **Google News API** - Access and search news articles from Google News
- **Google Trends API** - Retrieve trending topics and search interest data
- **Google Autocomplete API** - Get search suggestions and keyword variations
- **YouTube Transcripts API** - Extract transcripts from YouTube videos
- **API Versioning** - All endpoints follow `/api/v1/` structure for future compatibility
- **RFC7807 Error Handling** - Standardized problem details for all error responses
- **Rate Limiting** - Configurable request throttling to prevent abuse
- **Comprehensive Health Checks** - Monitor system status and dependencies
- **Prometheus Metrics** - Track API usage and performance

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Google API credentials (see [GOOGLE_SERVICES.md](GOOGLE_SERVICES.md))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/social-flood.git
   cd social-flood
   ```

2. Copy the example environment file and configure your settings:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

4. The API is now running at http://localhost:8000

### API Documentation

- Swagger UI: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- ReDoc: [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)
- OpenAPI Schema: [http://localhost:8000/api/openapi.json](http://localhost:8000/api/openapi.json)

## Configuration

| Environment Variable | Description | Example |
|----------------------|-------------|---------|
| `API_KEYS` | Comma-separated list of valid API keys | `key1,key2,key3` |
| `ENABLE_API_KEY_AUTH` | Enable/disable API key authentication | `true` |
| `RATE_LIMIT_ENABLED` | Enable/disable rate limiting | `true` |
| `RATE_LIMIT_REQUESTS` | Number of requests allowed per timeframe | `100` |
| `RATE_LIMIT_TIMEFRAME` | Timeframe for rate limiting in seconds | `3600` |
| `ENABLE_CACHE` | Enable/disable response caching | `true` |
| `CACHE_TTL` | Cache time-to-live in seconds | `3600` |
| `REDIS_URL` | Redis connection URL for caching | `redis://redis:6379/0` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@db:5432/dbname` |
| `ENABLE_PROXY` | Enable/disable proxy for external requests | `false` |
| `PROXY_URL` | Proxy server URL | `http://proxy:8080` |
| `ENVIRONMENT` | Application environment | `development` |
| `DEBUG` | Enable/disable debug mode | `false` |
| `PROJECT_NAME` | Application name | `Social Flood` |
| `VERSION` | Application version | `1.0.0` |
| `DESCRIPTION` | Application description | `API for social media data aggregation` |

See [.env.example](.env.example) for a complete list of configuration options.

## Usage Examples

### Basic Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": 1622548800.123456
}
```

### Google News Search

```bash
curl -X GET "http://localhost:8000/api/v1/google-news/search?q=artificial+intelligence&country=US&language=en&max_results=5" \
  -H "x-api-key: your_api_key"
```

Response:
```json
{
  "status": "success",
  "query": "artificial intelligence",
  "country": "US",
  "language": "en",
  "results": [
    {
      "title": "Latest Developments in AI Research",
      "link": "https://example.com/ai-research",
      "source": "Tech News",
      "published": "2023-06-01T12:00:00Z",
      "snippet": "Researchers have made significant progress in..."
    },
    ...
  ]
}
```

### Google Autocomplete Suggestions

```bash
curl -X GET "http://localhost:8000/api/v1/google-autocomplete/autocomplete?q=python+programming&output=chrome&gl=US" \
  -H "x-api-key: your_api_key"
```

Response:
```json
{
  "response_type": "json",
  "original_query": "python programming",
  "suggestions": [
    "python programming tutorial",
    "python programming language",
    "python programming for beginners",
    "python programming jobs",
    "python programming examples"
  ],
  "metadata": {
    "google:clientdata": {"bpc": true, "tlw": false},
    "google:suggesttype": ["QUERY", "QUERY", "QUERY", "QUERY", "QUERY"],
    "google:verbatimrelevance": 1300
  }
}
```

For more examples, see [EXAMPLES.md](EXAMPLES.md).

## Documentation

- [API Structure](API_STRUCTURE.md) - Detailed API structure and organization
- [Google Services](GOOGLE_SERVICES.md) - How to integrate with Google services
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md) - High-level system architecture
- [Deployment](DEPLOYMENT.md) - Step-by-step deployment instructions
- [Security Guidelines](SECURITY_GUIDELINES.md) - Best practices and security considerations
- [Performance Tuning](PERFORMANCE_TUNING.md) - Tips for optimizing performance
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [API Reference](API_REFERENCE.md) - Complete endpoint reference
- [Changelog](CHANGELOG.md) - Version history and changes
- [Roadmap](ROADMAP.md) - Planned features and improvements
- [FAQ](FAQ.md) - Frequently asked questions

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
