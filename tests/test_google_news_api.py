import pytest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient

# Assuming your FastAPI app and router are structured to be importable
# If gnews_router is in app.api.google_news.google_news_api, and you have a main app instance
# For simplicity, we might need to create a local app instance for testing the router
from app.api.google_news.google_news_api import gnews_router, transform_article, decode_google_news_url, NewsArticle

# Setup a minimal FastAPI app for testing the router
app = FastAPI()
app.include_router(gnews_router, prefix="/news")


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
@pytest.mark.asyncio
async def test_get_top_google_news_success():
    # Mock GNews instance and its methods
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [
        {"title": "Top News 1", "url": "http://google.com/news/1", "publisher": {"title": "Pub1"}, "published date": "date1", "description": "desc1"},
        {"title": "Top News 2", "url": "http://google.com/news/2", "publisher": {"title": "Pub2"}, "published date": "date2", "description": "desc2"},
    ]

    expected_processed_articles = [
        NewsArticle(title="Top News 1", url="http://decoded.com/news/1", publisher="Pub1", published_date="date1", description="desc1").dict(),
        NewsArticle(title="Top News 2", url="http://decoded.com/news/2", publisher="Pub2", published_date="date2", description="desc2").dict(),
    ]
    
    # Patch get_gnews_instance and decode_and_process_articles
    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews, \
         patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock) as mock_decode_process:
        
        mock_get_gnews.return_value = mock_gnews_instance
        mock_decode_process.return_value = expected_processed_articles # Simulate that articles were successfully decoded

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/news/top/", params={"language": "en", "country": "US", "max_results": 2})

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


@pytest.mark.asyncio
async def test_get_top_google_news_gnews_returns_no_news():
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [] # GNews found no articles

    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews:
        mock_get_gnews.return_value = mock_gnews_instance

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/news/top/")
        
        assert response.status_code == 404
        assert response.json() == {"detail": "No top news found."}

@pytest.mark.asyncio
async def test_get_top_google_news_decode_returns_no_news():
    # Test case where GNews returns articles, but decode_and_process_articles returns empty
    mock_gnews_instance = MagicMock()
    mock_gnews_instance.get_top_news.return_value = [
        {"title": "Raw News 1", "url": "http://google.com/news/raw1"}
    ]

    with patch('app.api.google_news.google_news_api.get_gnews_instance', new_callable=AsyncMock) as mock_get_gnews, \
         patch('app.api.google_news.google_news_api.decode_and_process_articles', new_callable=AsyncMock) as mock_decode_process:
        
        mock_get_gnews.return_value = mock_gnews_instance
        mock_decode_process.return_value = [] # Simulate all articles failed decoding or were filtered

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/news/top/")
        
        assert response.status_code == 404
        # This detail comes from the new check in the endpoint after calling decode_and_process_articles
        assert response.json() == {"detail": "No processable top news found after URL decoding."}
        mock_decode_process.assert_called_once_with(mock_gnews_instance.get_top_news.return_value)

# TODO: Add tests for other endpoints (/source, /search, /topic, /location, /articles)
# TODO: Add tests for error conditions in decode_url, get_decoding_params, get_base64_str if testing them directly.
# For now, decode_google_news_url tests cover their orchestration.
# Need to mock get_proxy for the lower-level decoding functions if tested directly.
# For example, for get_decoding_params:
# @pytest.mark.asyncio
# @patch('app.api.google_news.google_news_api.get_proxy', new_callable=AsyncMock)
# @patch('httpx.AsyncClient.get') # This would be more involved
# async def test_get_decoding_params_direct(mock_httpx_get, mock_get_proxy):
#     mock_get_proxy.return_value = None # or a proxy URL
#     # ... setup mock_httpx_get response ...
#     # from app.api.google_news.google_news_api import get_decoding_params
#     # result = await get_decoding_params("some_base64_string")
#     # assert result ...
#     pass
