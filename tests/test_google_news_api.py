import pytest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Assuming your FastAPI app and router are structured to be importable
# If gnews_router is in app.api.google_news.google_news_api, and you have a main app instance
# For simplicity, we might need to create a local app instance for testing the router
from app.api.google_news.google_news_api import gnews_router, transform_article, decode_google_news_url, NewsArticle

# Setup a minimal FastAPI app for testing the router
app = FastAPI()
app.include_router(gnews_router, prefix="/news")
client = TestClient(app)


# 1. Test transform_article
def test_transform_article_success():
    raw_article = {
        "title": "Test Title",
        "description": "Test Description",
        "published date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": {"title": "Example Publisher"}
    }
    expected_transformed_article = {
        "title": "Test Title",
        "description": "Test Description",
        "published_date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": "Example Publisher"
    }
    assert transform_article(raw_article) == expected_transformed_article

def test_transform_article_missing_fields():
    raw_article = {
        "title": "Test Title Only",
        "url": "http://example.com/article_no_desc"
        # Missing description, published date, publisher
    }
    expected_transformed_article = {
        "title": "Test Title Only",
        "description": None,
        "published_date": None,
        "url": "http://example.com/article_no_desc",
        "publisher": None
    }
    assert transform_article(raw_article) == expected_transformed_article

def test_transform_article_publisher_none():
    raw_article = {
        "title": "Test Title",
        "published date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": None # Publisher field exists but is None
    }
    expected_transformed_article = {
        "title": "Test Title",
        "description": None,
        "published_date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": None
    }
    assert transform_article(raw_article) == expected_transformed_article

def test_transform_article_publisher_empty_dict():
    raw_article = {
        "title": "Test Title",
        "published date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": {} # Publisher is an empty dict
    }
    expected_transformed_article = {
        "title": "Test Title",
        "description": None,
        "published_date": "2023-01-01T12:00:00Z",
        "url": "http://example.com/article",
        "publisher": None
    }
    assert transform_article(raw_article) == expected_transformed_article


# 2. Test URL Decoding (decode_google_news_url)
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_base64_str', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.get_decoding_params', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_url', new_callable=AsyncMock)
async def test_decode_google_news_url_success(mock_decode_url, mock_get_decoding_params, mock_get_base64_str):
    mock_get_base64_str.return_value = {"status": True, "base64_str": "test_b64_str"}
    mock_get_decoding_params.return_value = {"status": True, "signature": "test_sig", "timestamp": "test_ts", "base64_str": "test_b64_str"}
    mock_decode_url.return_value = {"status": True, "decoded_url": "http://real-example.com"}

    source_url = "http://news.google.com/articles/test_b64_str"
    result = await decode_google_news_url(source_url)

    assert result == {"status": True, "decoded_url": "http://real-example.com"}
    mock_get_base64_str.assert_called_once_with(source_url)
    mock_get_decoding_params.assert_called_once_with("test_b64_str")
    mock_decode_url.assert_called_once_with("test_sig", "test_ts", "test_b64_str")

@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_base64_str', new_callable=AsyncMock)
async def test_decode_google_news_url_fail_base64(mock_get_base64_str):
    mock_get_base64_str.return_value = {"status": False, "message": "Invalid base64"}
    
    source_url = "http://invalid-google-news-url.com"
    result = await decode_google_news_url(source_url)

    assert result == {"status": False, "message": "Invalid base64"}
    mock_get_base64_str.assert_called_once_with(source_url)

@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_base64_str', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.get_decoding_params', new_callable=AsyncMock)
async def test_decode_google_news_url_fail_decoding_params(mock_get_decoding_params, mock_get_base64_str):
    mock_get_base64_str.return_value = {"status": True, "base64_str": "test_b64_str"}
    mock_get_decoding_params.return_value = {"status": False, "message": "Failed to get params"}

    source_url = "http://news.google.com/articles/test_b64_str"
    result = await decode_google_news_url(source_url)

    assert result == {"status": False, "message": "Failed to get params"}
    mock_get_decoding_params.assert_called_once_with("test_b64_str")


@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_base64_str', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.get_decoding_params', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_url', new_callable=AsyncMock)
async def test_decode_google_news_url_fail_decode_final_url(mock_decode_url, mock_get_decoding_params, mock_get_base64_str):
    mock_get_base64_str.return_value = {"status": True, "base64_str": "test_b64_str"}
    mock_get_decoding_params.return_value = {"status": True, "signature": "test_sig", "timestamp": "test_ts", "base64_str": "test_b64_str"}
    mock_decode_url.return_value = {"status": False, "message": "Failed to decode URL"}

    source_url = "http://news.google.com/articles/test_b64_str"
    result = await decode_google_news_url(source_url)

    assert result == {"status": False, "message": "Failed to decode URL"}


# 3. Test an API Endpoint (e.g., /top/)
def test_get_top_google_news_success():
    # Mock GNews instance and its methods
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [
        {"title": "Top News 1", "url": "http://google.com/news/1", "publisher": {"title": "Pub1"}, "published date": "date1", "description": "desc1"},
        {"title": "Top News 2", "url": "http://google.com/news/2", "publisher": {"title": "Pub2"}, "published date": "date2", "description": "desc2"},
    ]

    expected_processed_articles = [
        NewsArticle(title="Top News 1", url="http://decoded.com/news/1", publisher="Pub1", published_date="date1", description="desc1").model_dump(),
        NewsArticle(title="Top News 2", url="http://decoded.com/news/2", publisher="Pub2", published_date="date2", description="desc2").model_dump(),
    ]
    
    # Patch get_gnews_instance and decode_and_process_articles
    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews, \
         patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock) as mock_decode_process:
        
        mock_get_gnews.return_value = mock_gnews_instance
        mock_decode_process.return_value = expected_processed_articles # Simulate that articles were successfully decoded

        response = client.get("/news/top/", params={"language": "en", "country": "US", "max_results": 2})

        assert response.status_code == 200
        response_json = response.json()
        assert response_json == {"articles": expected_processed_articles}
        
        # Assert that get_gnews_instance was called with correct parameters from the endpoint
        mock_get_gnews.assert_called_once()
        call_args = mock_get_gnews.call_args[1] # Get kwargs
        assert call_args['language'] == 'en'
        assert call_args['country'] == 'US'
        assert call_args['max_results'] == 2
        
        # Assert that decode_and_process_articles was called with the raw articles from gnews
        mock_decode_process.assert_called_once_with(mock_gnews_instance.get_top_news.return_value)
        mock_gnews_instance.get_top_news.assert_called_once()


def test_get_top_google_news_gnews_returns_no_news():
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [] # GNews found no articles

    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews:
        mock_get_gnews.return_value = mock_gnews_instance

        response = client.get("/news/top/")
        
        assert response.status_code == 404
        assert response.json() == {"detail": "No top news found."}

def test_get_top_google_news_decode_returns_no_news():
    # Test case where GNews returns articles, but decode_and_process_articles returns empty
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [
        {"title": "Raw News 1", "url": "http://google.com/news/raw1"}
    ]

    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews, \
         patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock) as mock_decode_process:
        
        mock_get_gnews.return_value = mock_gnews_instance
        mock_decode_process.return_value = [] # Simulate all articles failed decoding or were filtered

        response = client.get("/news/top/")
        
        assert response.status_code == 404
        # This detail comes from the new check in the endpoint after calling decode_and_process_articles
        assert response.json() == {"detail": "No processable top news found after URL decoding."}
        mock_decode_process.assert_called_once_with(mock_gnews_instance.get_top_news.return_value)

# Additional comprehensive tests to increase coverage

# Test available languages endpoint
def test_get_languages():
    response = client.get("/news/available-languages/")
    assert response.status_code == 200
    data = response.json()
    assert "available_languages" in data
    assert isinstance(data["available_languages"], dict)
    assert "english" in data["available_languages"]


# Test available countries endpoint
def test_get_available_countries():
    response = client.get("/news/available-countries/")
    assert response.status_code == 200
    data = response.json()
    assert "available_countries" in data
    assert isinstance(data["available_countries"], dict)
    assert "United States" in data["available_countries"]


# Test /source/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock)
async def test_get_news_by_source_success(mock_decode_process, mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news_by.return_value = [
        {"title": "Source News", "url": "http://google.com/news/source1", "publisher": {"title": "SourcePub"}}
    ]
    mock_get_gnews.return_value = mock_gnews_instance
    mock_decode_process.return_value = [
        NewsArticle(title="Source News", url="http://decoded.com/news/source1", publisher="SourcePub", published_date="2023-01-01", description="Test description").model_dump()
    ]

    response = client.get("/news/source/", params={
        "source": "cnn.com",
        "language": "en",
        "country": "US",
        "max_results": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data
    assert len(data["articles"]) == 1


@pytest.mark.asyncio
async def test_get_news_by_source_invalid_source():
    # Test with invalid source
    response = client.get("/news/source/", params={"source": "invalid-source"})
    assert response.status_code == 400  # Validation error


# Test /search/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock)
async def test_search_google_news_success(mock_decode_process, mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news.return_value = [
        {"title": "Search Result", "url": "http://google.com/news/search1", "publisher": {"title": "SearchPub"}}
    ]
    mock_get_gnews.return_value = mock_gnews_instance
    mock_decode_process.return_value = [
        NewsArticle(title="Search Result", url="http://decoded.com/news/search1", publisher="SearchPub", published_date="2023-01-01", description="Test description").model_dump()
    ]

    response = client.get("/news/search/", params={
        "query": "test query",
        "language": "en",
        "country": "US",
        "max_results": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data


@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
async def test_search_google_news_no_results(mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news.return_value = []
    mock_get_gnews.return_value = mock_gnews_instance

    response = client.get("/news/search/", params={"query": "nonexistent"})
    assert response.status_code == 404


# Test /topic/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock)
async def test_get_news_by_topic_success(mock_decode_process, mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news_by_topic.return_value = [
        {"title": "Topic News", "url": "http://google.com/news/topic1", "publisher": {"title": "TopicPub"}}
    ]
    mock_get_gnews.return_value = mock_gnews_instance
    mock_decode_process.return_value = [
        NewsArticle(title="Topic News", url="http://decoded.com/news/topic1", publisher="TopicPub", published_date="2023-01-01", description="Test description").model_dump()
    ]

    response = client.get("/news/topic/", params={
        "topic": "WORLD",
        "language": "en",
        "country": "US",
        "max_results": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data


# Test /location/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock)
async def test_get_news_by_location_success(mock_decode_process, mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news_by_location.return_value = [
        {"title": "Location News", "url": "http://google.com/news/location1", "publisher": {"title": "LocationPub"}}
    ]
    mock_get_gnews.return_value = mock_gnews_instance
    mock_decode_process.return_value = [
        NewsArticle(title="Location News", url="http://decoded.com/news/location1", publisher="LocationPub", published_date="2023-01-01", description="Test description").model_dump()
    ]

    response = client.get("/news/location/", params={
        "location": "New York",
        "language": "en",
        "country": "US",
        "max_results": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data


# Test /articles/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
@patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock)
async def test_get_google_news_articles_success(mock_decode_process, mock_get_gnews):
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_news.return_value = [
        {"title": "Bulk Article", "url": "http://google.com/news/bulk1", "publisher": {"title": "BulkPub"}}
    ]
    mock_get_gnews.return_value = mock_gnews_instance
    mock_decode_process.return_value = [
        NewsArticle(title="Bulk Article", url="http://decoded.com/news/bulk1", publisher="BulkPub", published_date="2023-01-01", description="Test description").model_dump()
    ]

    response = client.get("/news/articles/", params={
        "query": "test",
        "country": "US",
        "language": "en",
        "period": "7d",
        "max_results": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "articles" in data


# Test /article-details/ endpoint
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.Article')
async def test_get_article_details_success(mock_article_class):
    # Create a mock article instance
    mock_article = MagicMock()
    mock_article.title = "Test Article Title"
    mock_article.text = "Test article content"
    mock_article.summary = "Test summary"
    mock_article.authors = ["Test Author"]
    mock_article.publish_date = "2023-01-01"
    mock_article.top_image = "http://example.com/image.jpg"
    mock_article.keywords = ["test", "article"]
    mock_article.images = set()
    mock_article.movies = []
    mock_article.meta_data = {}
    mock_article.meta_description = ""
    mock_article.meta_keywords = ""
    
    # Mock the synchronous methods
    mock_article.download = MagicMock()
    mock_article.parse = MagicMock()
    mock_article.nlp = MagicMock()
    
    # Make the Article constructor return our mock
    mock_article_class.return_value = mock_article

    response = client.get("/news/article-details/", params={"url": "http://example.com/article"})

    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "text" in data
    assert data["title"] == "Test Article Title"
# Test helper functions
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.cache_manager')
@patch('app.api.google_news.google_news_api.settings')
async def test_get_cached_or_fetch_cache_hit(mock_settings, mock_cache_manager):
    mock_settings.ENABLE_CACHE = True
    mock_cache_manager.get = AsyncMock(return_value={"cached": "data"})

    from app.api.google_news.google_news_api import get_cached_or_fetch

    async def dummy_fetch():
        return {"fresh": "data"}

    result = await get_cached_or_fetch("test_key", dummy_fetch)
    assert result == {"cached": "data"}
    mock_cache_manager.get.assert_called_once_with("test_key", namespace="gnews")


@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.cache_manager')
@patch('app.api.google_news.google_news_api.settings')
async def test_get_cached_or_fetch_cache_miss(mock_settings, mock_cache_manager):
    mock_settings.ENABLE_CACHE = True
    mock_cache_manager.get = AsyncMock(return_value=None)
    mock_cache_manager.set = AsyncMock()

    from app.api.google_news.google_news_api import get_cached_or_fetch

    async def dummy_fetch():
        return {"fresh": "data"}

    result = await get_cached_or_fetch("test_key", dummy_fetch)
    assert result == {"fresh": "data"}
    mock_cache_manager.set.assert_called_once()


@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.settings')
async def test_get_cached_or_fetch_cache_disabled(mock_settings):
    mock_settings.ENABLE_CACHE = False

    from app.api.google_news.google_news_api import get_cached_or_fetch

    async def dummy_fetch():
        return {"fresh": "data"}

    result = await get_cached_or_fetch("test_key", dummy_fetch)
    assert result == {"fresh": "data"}


# Test generate_cache_key function
def test_generate_cache_key():
    from app.api.google_news.google_news_api import generate_cache_key

    key = generate_cache_key("test_endpoint", param1="value1", param2="value2")
    assert "gnews:test_endpoint:" in key
    assert "param1:value1" in key
    assert "param2:value2" in key


# Test SourceQuery model validation
def test_source_query_valid():
    from app.api.google_news.google_news_api import SourceQuery

    source = SourceQuery(source="cnn.com")
    assert source.source == "cnn.com"


def test_source_query_invalid():
    from app.api.google_news.google_news_api import SourceQuery

    with pytest.raises(ValidationError):
        SourceQuery(source="invalid-source")


# Test NewsArticle model
def test_news_article_model():
    article = NewsArticle(
        title="Test Title",
        url="http://example.com",
        publisher="Test Publisher",
        published_date="2023-01-01",
        description="Test description"
    )
    assert article.title == "Test Title"
    assert article.url == "http://example.com"


# Test error responses
@pytest.mark.asyncio
@patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock)
async def test_get_top_google_news_internal_error(mock_get_gnews):
    mock_get_gnews.side_effect = Exception("Internal error")

    response = client.get("/news/top/")
    assert response.status_code == 500
    assert "Internal Server Error" in response.json()["detail"]


# Test parameter validation
def test_search_parameters_validation():
    # Test max_results bounds
    response = client.get("/news/search/", params={"query": "test", "max_results": 150})
    assert response.status_code == 422  # Should fail validation

    response = client.get("/news/search/", params={"query": "test", "max_results": 0})
    assert response.status_code == 422  # Should fail validation


# Test date parameter validation
def test_date_parameter_validation():
    response = client.get("/news/search/", params={
        "query": "test",
        "start_date": "invalid-date"
    })
    assert response.status_code == 422


# Test sort_by parameter validation
def test_sort_by_parameter_validation():
    response = client.get("/news/search/", params={
        "query": "test",
        "sort_by": "invalid_sort"
    })
    assert response.status_code == 422
