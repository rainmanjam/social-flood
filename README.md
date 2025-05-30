# Social Flood Docker API

A Docker-containerized FastAPI application that provides secure API access to various Google services including Google News, Google Trends, Google Autocomplete, and YouTube Transcripts, enabling comprehensive data collection and analysis for social media, news, and search trends.

## Features

- **Comprehensive Google Integration**: Access multiple Google services with a single API
- **Google News API**: Fetch, decode, and analyze news articles categorized by topics, regions, or sources
- **Google Trends API**: Analyze search trends over time, by region, and by related queries or topics
- **Google Autocomplete API**: Generate keyword variations using Google Autocomplete suggestions
- **YouTube Transcripts API**: Extract and translate YouTube video transcripts
- **API Key Authentication**: Secure your API with x-api-key header authentication
- **Rate Limiting**: Prevent abuse with configurable rate limits
- **Caching**: Improve performance with response caching
- **Proxy Support**: Configure global proxies via environment variables
- **Customizable Defaults**: Set default search parameters via environment variables
- **CORS Support**: Enable cross-origin requests for frontend integration
- **Health Checks**: Monitor application health with dedicated endpoints
- **Comprehensive Logging**: Track API usage and troubleshoot issues

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=rainmanjam/social-flood&type=Date)](https://www.star-history.com/#rainmanjam/social-flood&Date)

## Support the Project

If you find Social Flood Docker API useful, please consider:
- ⭐️ Star this repository on GitHub: https://github.com/rainmanjam/social-flood
- 🍴 Fork it to contribute and customize.
- 👤 Follow the repo to stay updated with new features and releases.
- 📥 Pull the Docker image from Docker Hub:
```bash
  docker pull rainmanjam/social-flood:latest
```
  or visit https://hub.docker.com/r/rainmanjam/social-flood and doing the same there.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (optional, but recommended)

### Running with Docker

#### Build and run the Docker container

```bash
# Build the Docker image
docker build -t social-flood .

# Run the container
docker run -p 8000:8000 \
  -e API_KEY=your-api-key-1 \
  social-flood
```

#### Additional Docker run options

You can configure the application by passing environment variables:

```bash
docker run -p 8000:8000 \
  -e API_KEY=your-api-key \
  -e PROXY_URLS=user:pass@host:port,user:pass@host:port \
  -e ENABLE_PROXY=true \
  -e LOG_LEVEL=INFO \
  social-flood
```

### Running with Docker Compose

#### Production setup

1. Edit the environment variables in `docker-compose.yml` to match your requirements:

```yaml
environment:
  # API Security
  - API_KEY=your-api-key
  
  # Proxy Configuration (if needed)
  - PROXY_URLS=user:pass@host:port,user:pass@host:port
  - ENABLE_PROXY=true
  
  # Other settings as needed
  - LOG_LEVEL=INFO
```

2. Start the application with Docker Compose:

```bash
docker-compose up -d
```

3. Access the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs)

#### Development setup

For development with auto-reload:

```bash
# Uses docker-compose.dev.yml which mounts local directory and enables auto-reload
docker-compose -f docker-compose.dev.yml up
```

### Stopping the application

```bash
# If running with docker-compose
docker-compose down

# If running with docker
docker stop <container_id>
```

## Installation

### Prerequisites

- Python 3.8 or higher

### Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/rainmanjam/social-flood.git
   cd social-flood
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Define the following in a `.env` file or your environment:
   - `API_KEY` (for securing API access)
   - Optional: `PROXY_URLS`, `ENABLE_PROXY`, `ENABLE_CACHE`

4. **Run the Application**:
   ```bash
   uvicorn main:app --reload
   ```

   The application will be accessible at `http://127.0.0.1:8000`.

## Configuration

### Environment Variables

You can configure the application using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| **API Security** | | |
| API_KEY | API key for securing access | None |
| **Proxy Configuration** | | |
| PROXY_URLS | Comma-separated proxy URLs | [] |
| ENABLE_PROXY | Enable proxy usage | false |
| CA_CERT_PATH | Path to CA Certificate file for proxies | null |
| **Caching** | | |
| ENABLE_CACHE | Enable response caching | true |
| CACHE_EXPIRY | Cache expiry time in seconds | 3600 |
| **Logging & CORS** | | |
| LOG_LEVEL | Logging level (INFO, DEBUG, etc.) | INFO |
| ENVIRONMENT | Environment name (development, production) | development |
| CORS_ORIGINS | Allowed origins for CORS | * |

### Example `.env` File
```ini
API_KEY=your_api_key
ENABLE_PROXY=true
PROXY_URLS=http://proxy1.com,http://proxy2.com
LOG_LEVEL=INFO
```

## API Usage

All API endpoints require an API key to be passed in the `x-api-key` header.

### Google News API

1. **Search News**
   - **Endpoint**: `/google-news/search`
   - **Method**: `GET`
   - **Description**: Searches Google News for articles matching a query.
   - **Params**: 
     - `query` (string): The search query string
     - `language` (string, optional): Language for the news results (default: 'en')
     - `country` (string, optional): Country for the news results (default: 'US')
     - `max_results` (int, optional): Maximum number of news results (1-100)
     - `start_date` (string, optional): Start date in YYYY-MM-DD format
     - `end_date` (string, optional): End date in YYYY-MM-DD format
     - `exclude_duplicates` (bool, optional): Exclude duplicate news articles
     - `exact_match` (bool, optional): Search for an exact match of the query
     - `sort_by` (string, optional): Sort news by 'relevance' or 'date'

2. **Top News**
   - **Endpoint**: `/google-news/top`
   - **Method**: `GET`
   - **Description**: Fetches the top Google News articles.
   - **Params**: 
     - `language` (string, optional): Language for the news results (default: 'en')
     - `country` (string, optional): Country for the news results (default: 'US')
     - `max_results` (int, optional): Maximum number of news results (1-100)

3. **News by Topic**
   - **Endpoint**: `/google-news/topic`
   - **Method**: `GET`
   - **Description**: Fetches news articles based on a specific topic.
   - **Params**: 
     - `topic` (string): The topic to filter news articles
     - `language` (string, optional): Language for the news results
     - `country` (string, optional): Country for the news results
     - `max_results` (int, optional): Maximum number of news results
     - `exclude_duplicates` (bool, optional): Exclude duplicate news articles

4. **News by Location**
   - **Endpoint**: `/google-news/location`
   - **Method**: `GET`
   - **Description**: Fetches news articles relevant to a specific location.
   - **Params**: 
     - `location` (string): The location to filter news articles
     - `language` (string, optional): Language for the news results
     - `country` (string, optional): Country for the news results
     - `max_results` (int, optional): Maximum number of news results
     - `start_date` (string, optional): Start date in YYYY-MM-DD format
     - `end_date` (string, optional): End date in YYYY-MM-DD format
     - `exclude_duplicates` (bool, optional): Exclude duplicate news articles

5. **News by Source**
   - **Endpoint**: `/google-news/source`
   - **Method**: `GET`
   - **Description**: Fetches news articles from a specific source.
   - **Params**: 
     - `source` (string): Source domain or full URL
     - `language` (string, optional): Language for the news results
     - `country` (string, optional): Country for the news results
     - `max_results` (int, optional): Maximum number of news results
     - `exclude_duplicates` (bool, optional): Exclude duplicate news articles
     - `start_date` (string, optional): Start date in YYYY-MM-DD format
     - `end_date` (string, optional): End date in YYYY-MM-DD format

6. **Article Details**
   - **Endpoint**: `/google-news/article-details`
   - **Method**: `GET`
   - **Description**: Retrieves detailed information about a specific article.
   - **Params**: 
     - `url` (string): URL of the article to retrieve details for

### Google Trends API

1. **Interest Over Time**
   - **Endpoint**: `/google-trends/interest-over-time`
   - **Method**: `GET`
   - **Description**: Retrieves Google Trends interest over time for specified keywords.
   - **Params**: 
     - `keywords` (string): Comma-separated keywords
     - `timeframe` (string, optional): Timeframe for the query (default: 'today 12-m')
     - `geo` (string, optional): Geolocation code
     - `cat` (string, optional): Category ID
     - `gprop` (string, optional): Google property

2. **Interest By Region**
   - **Endpoint**: `/google-trends/interest-by-region`
   - **Method**: `GET`
   - **Description**: Retrieves Google Trends interest by region for a keyword.
   - **Params**: 
     - `keyword` (string): Single keyword
     - `timeframe` (string, optional): Timeframe
     - `geo` (string, optional): Geolocation code
     - `cat` (string, optional): Category ID
     - `resolution` (string, optional): Resolution level (COUNTRY, REGION, CITY)

3. **Related Queries**
   - **Endpoint**: `/google-trends/related-queries`
   - **Method**: `GET`
   - **Description**: Retrieves related queries for a specified keyword.
   - **Params**: 
     - `keyword` (string): Single keyword
     - `timeframe` (string, optional): Timeframe
     - `geo` (string, optional): Geolocation code
     - `cat` (string, optional): Category ID
     - `gprop` (string, optional): Google property

4. **Related Topics**
   - **Endpoint**: `/google-trends/related-topics`
   - **Method**: `GET`
   - **Description**: Retrieves related topics for a specified keyword.
   - **Params**: 
     - `keyword` (string): Single keyword
     - `timeframe` (string, optional): Timeframe
     - `geo` (string, optional): Geolocation code
     - `cat` (string, optional): Category ID
     - `gprop` (string, optional): Google property

5. **Trending Now**
   - **Endpoint**: `/google-trends/trending-now`
   - **Method**: `GET`
   - **Description**: Retrieves current trending searches for the specified geo.
   - **Params**: 
     - `geo` (string, optional): Geolocation code for trending searches (default: 'US')

6. **Trending Now by RSS**
   - **Endpoint**: `/google-trends/trending-now-by-rss`
   - **Method**: `GET`
   - **Description**: Retrieves current trending searches by RSS for the specified geo.
   - **Params**: 
     - `geo` (string, optional): Geolocation code for trending searches (default: 'US')

7. **Categories**
   - **Endpoint**: `/google-trends/categories`
   - **Method**: `GET`
   - **Description**: Searches or lists categories in the Google Trends taxonomy.
   - **Params**: 
     - `find` (string, optional): String to match category name
     - `root` (string, optional): Root category ID to list subcategories

8. **Geo**
   - **Endpoint**: `/google-trends/geo`
   - **Method**: `GET`
   - **Description**: Searches available geolocation codes in Google Trends.
   - **Params**: 
     - `find` (string, optional): String to match location name

### Google Autocomplete API

1. **Autocomplete Keywords**
   - **Endpoint**: `/google-autocomplete/autocomplete-keywords`
   - **Method**: `GET`
   - **Description**: Generates keyword variations using Google Autocomplete.
   - **Params**: 
     - `input_keyword` (string): Base keyword to generate variations
     - `input_country` (string, optional): Country code for Google Autocomplete (default: 'US')
     - `output` (string): Output format (toolbar, chrome, firefox, xml, safari, opera)
     - `spell` (int, optional): Controls spell-checking (1 to enable, 0 to disable)
     - `hl` (string, optional): UI language setting (default: 'en')
     - `ds` (string, optional): Search domain or vertical

### YouTube Transcripts API

1. **Get Transcript**
   - **Endpoint**: `/youtube-transcripts/get-transcript`
   - **Method**: `GET`
   - **Description**: Retrieves the transcript for a YouTube video.
   - **Params**: 
     - `video_id` (string): YouTube video ID
     - `languages` (list, optional): List of language codes in descending priority (default: ['en'])
     - `preserve_formatting` (bool, optional): Preserve HTML formatting in transcripts

2. **List Transcripts**
   - **Endpoint**: `/youtube-transcripts/list-transcripts`
   - **Method**: `GET`
   - **Description**: Lists available transcripts for a YouTube video.
   - **Params**: 
     - `video_id` (string): YouTube video ID

3. **Translate Transcript**
   - **Endpoint**: `/youtube-transcripts/translate-transcript`
   - **Method**: `GET`
   - **Description**: Translates a YouTube video transcript.
   - **Params**: 
     - `video_id` (string): YouTube video ID
     - `target_language` (string): Target language code for translation
     - `source_languages` (list, optional): List of source language codes (default: ['en'])

4. **Batch Get Transcripts**
   - **Endpoint**: `/youtube-transcripts/batch-get-transcripts`
   - **Method**: `POST`
   - **Description**: Retrieves transcripts for multiple YouTube videos.
   - **Params**: 
     - `video_ids` (list): List of YouTube video IDs
     - `languages` (list, optional): List of language codes in descending priority
     - `preserve_formatting` (bool, optional): Preserve HTML formatting in transcripts

5. **Format Transcript**
   - **Endpoint**: `/youtube-transcripts/format-transcript`
   - **Method**: `GET`
   - **Description**: Formats the transcript of a YouTube video into the desired format.
   - **Params**: 
     - `video_id` (string): YouTube video ID
     - `format_type` (string): Desired format type (json, txt, vtt, srt, csv)
     - `languages` (list, optional): List of language codes in descending priority

## CLI Usage

Fetch Google Trends data:
```bash
python cli.py --google-trends "keyword1,keyword2"
```

## Development

### Run Tests
```bash
pytest
```

### Code Formatting
```bash
black .
```

## Troubleshooting

### API Issues
- If you receive a 429 error, you've exceeded the rate limit or the underlying Google services are blocking requests
- For high-volume usage, configure proxies to avoid being blocked
- Some Google services may have usage limitations or require additional authentication

### Docker Troubleshooting

- **Container exits immediately**: Check the logs with `docker logs <container_id>`
- **Can't access the API**: Make sure ports are correctly mapped and the container is running
- **API key issues**: Ensure API_KEY environment variable is set correctly
- **Proxy issues**: If using proxies, make sure they're correctly formatted and working
- **Permission issues**: If mounting volumes, ensure proper permissions are set

### Environment Variable Issues

If you're experiencing issues with environment variables:

1. **Verify variable values**: Check which values are active
   ```bash
   python scripts/check_env.py
   ```

2. **Docker environment**: When running in Docker, use this command to debug
   ```bash
   docker-compose exec social-flood bash -c "env | grep -E 'API_KEY|ENABLE_|LOG_LEVEL'"
   ```

3. **Inspect container**: If necessary, inspect the container directly
   ```bash
   docker-compose exec social-flood bash
   ```

### Common Issues and Solutions

1. **API authentication not working**:
   - Ensure `API_KEY` is set correctly
   - Verify you're including the proper header in requests (`x-api-key`)

2. **Container fails to start**:
   - Check logs with `docker-compose logs social-flood`
   - Try running with the debug configuration: `docker-compose -f docker-compose.dev.yml up`

3. **API errors with 500 status code**:
   - Check Docker logs for detailed error information
   - Increase logging level: `LOG_LEVEL=DEBUG`
   - Look for specific errors related to Google services

4. **Changes to `.env` file not taking effect**:
   - Remember Docker Compose may have overriding environment variables
   - Rebuild container: `docker-compose build` then `docker-compose up -d`

## Contributing

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.

## Known Issues

- High-volume API requests may require careful proxy management and caching strategies.
- Google APIs may have rate limits or specific terms of use.
- Some Google services may require additional authentication or API keys.

## License

This project is licensed under the MIT License.
