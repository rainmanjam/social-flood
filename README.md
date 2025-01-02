# Social Flood

## Overview

**Social Flood** is a comprehensive FastAPI-based application designed to integrate seamlessly with Google Ads, Google News, and Google Trends. It provides robust functionality for data extraction, processing, and analysis, empowering users with actionable insights into marketing campaigns, news trends, and search behaviors.

## Features

- **Google Ads API (coming soon)**: Manage and retrieve detailed data on ad accounts, ad groups, conversions, campaigns, and more.
- **Google News API**: Fetch, decode, and analyze news articles categorized by topics, regions, or sources.
- **Google Trends API (coming soon)**: Analyze search trends over time, by region, and by related queries or topics.
- **Proxy Support**: Configurable proxies enhance security and manage network requests.
- **Asynchronous Database Access (coming soon)**: Efficiently manage data with async SQLAlchemy.
- **CLI Access**: Quickly interact with Google Trends data via the command-line interface.
- **Modular Design**: Easy to extend and maintain with modular APIs and clear code structure.

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

### Docker Setup (Optional)

1. **Build the Docker Image**:
   ```bash
   docker build -t social-flood .
   ```

2. **Run the Container**:
   ```bash
   docker run -d -p 8000:8000 --env-file .env social-flood
   ```

## Usage

### CLI Example

Fetch Google Trends data:
```bash
python cli.py --google-trends "keyword1,keyword2"
```

### API Documentation

#### Google News API

1. **Search News**
   - **Endpoint**: `/google-news/search`
   - **Method**: `GET`
   - **Description**: Searches Google News for articles matching a query.
   - **Params**: 
     - `query` (string)
     - Optional: `language`, `country`, `max_results`, `start_date`, `end_date`, etc.

2. **Top News**
   - **Endpoint**: `/google-news/top`
   - **Method**: `GET`
   - **Description**: Fetches the top Google News articles.
   - **Params**: 
     - Optional: `language`, `country`, `max_results`

3. **News by Topic**
   - **Endpoint**: `/google-news/topic`
   - **Method**: `GET`
   - **Description**: Fetches news articles based on a specific topic.
   - **Params**: 
     - `topic` (string)

4. **News by Location**
   - **Endpoint**: `/google-news/location`
   - **Method**: `GET`
   - **Description**: Fetches news articles relevant to a specific location.
   - **Params**: 
     - `location` (string)

5. **News by Source**
   - **Endpoint**: `/google-news/source`
   - **Method**: `GET`
   - **Description**: Fetches news articles from a specific source.
   - **Params**: 
     - `source` (string)

6. **Article Details**
   - **Endpoint**: `/google-news/article-details`
   - **Method**: `GET`
   - **Description**: Retrieves detailed information about a specific article.
   - **Params**: 
     - `url` (string)

## Configuration

### Environment Variables

- **Database Configuration**:
  - `DATABASE_URL`: PostgreSQL connection string
  
- **Proxy Configuration**:
  - `PROXY_URLS`: Comma-separated proxy URLs
  - `ENABLE_PROXY`: Set to `true` to enable proxy usage
  
- **Caching**:
  - `ENABLE_CACHE`: Set to `true` to enable Redis-based caching
  - `REDIS_URL`: Redis connection string

### Example `.env` File
```ini
API_KEY=your_api_key
ENABLE_PROXY=true
PROXY_URLS=http://proxy1.com,http://proxy2.com
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

## Contributing

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.

## Known Issues

- High-volume API requests may require careful proxy management and caching strategies.
- Google APIs may have rate limits or specific terms of use.

## License

This project is licensed under the MIT License.