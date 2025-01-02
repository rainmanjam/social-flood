from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from gnews import GNews
from newspaper import Article, Config
from typing import List, Optional
import logging
import json
import asyncio
from urllib.parse import quote, urlparse
import httpx
from selectolax.parser import HTMLParser
import nltk
from pydantic import BaseModel, validator, ValidationError
import re
from app.core.proxy import get_proxy  # adjust if needed
import datetime

# Initialize NLTK asynchronously
async def setup_nltk():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, nltk.download, 'punkt_tab')

# Initialize Google News API Router
gnews_router = APIRouter()
logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.DEBUG)  # Ensure DEBUG level logs are captured

# Pydantic Model for Input Validation
class SourceQuery(BaseModel):
    source: str

    @validator('source')
    def validate_source(cls, v):
        # Optimized regex to validate domain names or full URLs
        pattern = r'^(https?://)?(www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$'
        if not re.fullmatch(pattern, v):
            raise ValueError('Invalid source URL or domain.')
        return v

AVAILABLE_TOPICS = [
    "WORLD", "NATION", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"
]

AVAILABLE_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ar"
]

AVAILABLE_COUNTRIES = [
    "US", "GB", "CA", "AU", "IN", "DE", "FR", "IT", "ES", "RU", "CN", "JP", "BR", "ZA"
]

# -----------------------------------------------------------------------------
# Helper: Create an AsyncClient with or without proxy mounts
# -----------------------------------------------------------------------------
def create_async_client_with_proxy(proxy_url: Optional[str] = None, follow_redirects: bool = True):
    """
    Create and return an httpx.AsyncClient. 
    If proxy_url is provided, set up mounts for HTTP and HTTPS.
    """
    if proxy_url:
        mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=proxy_url),
            "https://": httpx.AsyncHTTPTransport(proxy=proxy_url),
        }
        return httpx.AsyncClient(mounts=mounts, follow_redirects=follow_redirects)
    else:
        return httpx.AsyncClient(follow_redirects=follow_redirects)

# -----------------------------------------------------------------------------
# Decoding functions
# -----------------------------------------------------------------------------
async def get_base64_str(source_url):
    """
    Extracts the base64 string from a Google News URL.
    """
    try:
        url = urlparse(source_url)
        path = url.path.split("/")
        if (
            url.hostname == "news.google.com"
            and len(path) > 1
            and path[-2] in ["articles", "read", "rss"]
        ):
            return {"status": True, "base64_str": path[-1]}
        return {"status": False, "message": "Invalid Google News URL format."}
    except Exception as e:
        return {"status": False, "message": f"Error in get_base64_str: {str(e)}"}

async def get_decoding_params(base64_str):
    """
    Fetches signature and timestamp required for decoding from Google News.
    """
    try:
        url = f"https://news.google.com/rss/articles/{base64_str}"
        proxy_url = await get_proxy()  # Adjust based on your implementation

        async with create_async_client_with_proxy(proxy_url=proxy_url) as client:
            response = await client.get(url)
        response.raise_for_status()

        parser = HTMLParser(response.text)
        data_element = parser.css_first("c-wiz > div[jscontroller]")
        if data_element is None:
            return {
                "status": False,
                "message": "Failed to fetch data attributes from Google News with the RSS URL.",
            }

        return {
            "status": True,
            "signature": data_element.attributes.get("data-n-a-sg"),
            "timestamp": data_element.attributes.get("data-n-a-ts"),
            "base64_str": base64_str,
        }

    except httpx.RequestError as rss_req_err:
        return {
            "status": False,
            "message": f"Request error in get_decoding_params with RSS URL: {str(rss_req_err)}",
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Unexpected error in get_decoding_params: {str(e)}",
        }

def validate_date_format(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

async def decode_url(signature, timestamp, base64_str, start_date=None, end_date=None):
    """
    Decodes the Google News URL using the signature and timestamp.
    """
    try:
        # Validate date formats
        if start_date and not validate_date_format(start_date):
            logger.error(f"Invalid start_date format: {start_date}. Expected format: YYYY-MM-DD")
            return {
                "status": False,
                "message": f"Invalid start_date format: {start_date}. Expected format: YYYY-MM-DD",
            }
        if end_date and not validate_date_format(end_date):
            logger.error(f"Invalid end_date format: {end_date}. Expected format: YYYY-MM-DD")
            return {
                "status": False,
                "message": f"Invalid end_date format: {end_date}. Expected format: YYYY-MM-DD",
            }

        url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        payload = [
            "Fbv4je",
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{base64_str}",{timestamp},"{signature}"]',
        ]
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            ),
        }

        proxy_url = await get_proxy()  # Adjust based on your implementation

        async with create_async_client_with_proxy(proxy_url=proxy_url) as client:
            response = await client.post(
                url,
                headers=headers,
                data=f"f.req={quote(json.dumps([[payload]]))}"
            )
        response.raise_for_status()

        parsed_data = json.loads(response.text.split("\n\n")[1])[:-2]
        decoded_url = json.loads(parsed_data[0][2])[1]
        return {"status": True, "decoded_url": decoded_url}
    except httpx.RequestError as req_err:
        logger.error(f"Request error in decode_url: {str(req_err)}")
        return {
            "status": False,
            "message": f"Request error in decode_url: {str(req_err)}",
        }
    except (json.JSONDecodeError, IndexError, TypeError) as parse_err:
        logger.error(f"Parsing error in decode_url: {str(parse_err)}")
        return {
            "status": False,
            "message": f"Parsing error in decode_url: {str(parse_err)}",
        }
    except Exception as e:
        logger.error(f"Error in decode_url: {str(e)}")
        return {"status": False, "message": f"Error in decode_url: {str(e)}"}

async def decode_google_news_url(source_url, interval=None):
    """
    Decodes a Google News article URL into its original source URL.
    """
    try:
        base64_response = await get_base64_str(source_url)
        if not base64_response["status"]:
            return base64_response

        decoding_params_response = await get_decoding_params(base64_response["base64_str"])
        if not decoding_params_response["status"]:
            return decoding_params_response

        decoded_url_response = await decode_url(
            decoding_params_response["signature"],
            decoding_params_response["timestamp"],
            decoding_params_response["base64_str"],
        )
        if interval:
            await asyncio.sleep(interval)

        return decoded_url_response
    except Exception as e:
        return {
            "status": False,
            "message": f"Error in decode_google_news_url: {str(e)}",
        }

# -----------------------------------------------------------------------------
# Helper function to create a new GNews instance per request
# -----------------------------------------------------------------------------
async def get_gnews_instance(
    language: str,
    country: str,
    max_results: int,
    exclude_duplicates: bool = False,
    exact_match: bool = False,
    sort_by: str = "relevance",
    period: Optional[str] = None,
    start_date: Optional[tuple] = None,
    end_date: Optional[tuple] = None,
) -> GNews:
    gnews = GNews()
    gnews.language = language
    gnews.country = country
    gnews.max_results = max_results
    gnews.exclude_duplicates = exclude_duplicates
    gnews.exact_match = exact_match
    gnews.sort_by = sort_by
    if period:
        gnews.period = period
    if start_date:
        gnews.start_date = start_date
    if end_date:
        gnews.end_date = end_date

    # Set up proxies for GNews if available
    proxy_url = await get_proxy()  # Adjust based on your implementation

    if proxy_url:
        mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=proxy_url),
            "https://": httpx.AsyncHTTPTransport(proxy=proxy_url),
        }
        gnews.session = httpx.AsyncClient(mounts=mounts)
        logger.debug(f"GNews is using proxy: {proxy_url}")
    else:
        gnews.session = httpx.AsyncClient()
        logger.debug("GNews is not using any proxy.")

    return gnews

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@gnews_router.get("/google-news/available-languages/", summary="Get Available Languages")
async def get_languages():
    """
    Get a list of available languages for Google News.
    """
    return {"available_languages": AVAILABLE_LANGUAGES}

@gnews_router.get("/google-news/available-countries/", summary="Get Available Countries")
async def get_available_countries():
    """
    Get a list of available countries for Google News.
    """
    return {"available_countries": AVAILABLE_COUNTRIES}

@gnews_router.get("/google-news/search/", summary="Search Google News")
async def search_google_news(
    query: str,
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, description="Maximum number of news results."),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)."),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
    exact_match: bool = Query(False, description="Search for exact match of the query."),
    sort_by: str = Query("relevance", description="Sort news by relevance or date."),
):
    """
    Search Google News articles based on a query string.
    """
    try:
        # Parse dates if provided
        start_date_tuple = tuple(map(int, start_date.split("-"))) if start_date else None
        end_date_tuple = tuple(map(int, end_date.split("-"))) if end_date else None

        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
            exact_match=exact_match,
            sort_by=sort_by,
            start_date=start_date_tuple,
            end_date=end_date_tuple,
        )

        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, gnews.get_news, query)

        if not news:
            raise HTTPException(status_code=404, detail="No news found for the given query.")

        # Decode URLs asynchronously
        tasks = []
        for article in news:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        for article, decoded_url_response in zip(news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return news
    except Exception as e:
        logger.error(f"Error fetching Google News for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/top/", summary="Get Top Google News")
async def get_top_google_news(
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(10, description="Maximum number of news results."),
):
    """
    Get the top Google News articles.
    """
    try:
        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
        )

        loop = asyncio.get_event_loop()
        top_news = await loop.run_in_executor(None, gnews.get_top_news)

        if not top_news:
            raise HTTPException(status_code=404, detail="No top news found.")

        # Decode URLs asynchronously
        tasks = []
        for article in top_news:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        for article, decoded_url_response in zip(top_news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return top_news
    except Exception as e:
        logger.error(f"Error fetching top Google News: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/topic/", summary="Get Google News by Topic")
async def get_news_by_topic(
    topic: str,
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, description="Maximum number of news results."),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)."),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
):
    """
    Get Google News articles based on a specific topic.
    """
    if topic.upper() not in AVAILABLE_TOPICS:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid topic provided.", "available_topics": AVAILABLE_TOPICS}
        )
    try:
        # Parse dates if provided
        start_date_tuple = tuple(map(int, start_date.split("-"))) if start_date else None
        end_date_tuple = tuple(map(int, end_date.split("-"))) if end_date else None

        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
            start_date=start_date_tuple,
            end_date=end_date_tuple,
        )

        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, gnews.get_news_by_topic, topic)

        if not news:
            raise HTTPException(status_code=404, detail="No news found for the given topic.")

        # Decode URLs asynchronously
        tasks = []
        for article in news:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        for article, decoded_url_response in zip(news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return news
    except Exception as e:
        logger.error(f"Error fetching Google News for topic '{topic}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/location/", summary="Get Google News by Location")
async def get_news_by_location(
    location: str,
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, description="Maximum number of news results."),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)."),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
):
    """
    Get Google News articles based on a specific location.
    """
    try:
        # Parse dates if provided
        start_date_tuple = tuple(map(int, start_date.split("-"))) if start_date else None
        end_date_tuple = tuple(map(int, end_date.split("-"))) if end_date else None

        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
            start_date=start_date_tuple,
            end_date=end_date_tuple,
        )

        loop = asyncio.get_event_loop()
        news_by_location = await loop.run_in_executor(None, gnews.get_news_by_location, location)

        if not news_by_location:
            raise HTTPException(status_code=404, detail=f"No news found for the location '{location}'.")

        # Decode URLs asynchronously
        tasks = []
        for article in news_by_location:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        for article, decoded_url_response in zip(news_by_location, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return news_by_location
    except Exception as e:
        logger.error(f"Error fetching Google News for location '{location}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/source/", summary="Get Google News by Source")
async def get_news_by_source(
    source: str = Query(..., description="Source domain or full URL (e.g., 'msnbc.com' or 'https://www.msnbc.com')"),
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, description="Maximum number of news results."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
):
    """
    Get Google News articles based on a specific source.
    """
    try:
        # Validate input
        try:
            validated_query = SourceQuery(source=source)
            logger.debug(f"Validated source: {validated_query.source}")
        except ValidationError as ve:
            logger.error(f"Validation error for source '{source}': {ve}")
            raise HTTPException(status_code=400, detail="Invalid source URL or domain.")

        # Normalize the source input by extracting the domain if a URL is provided
        parsed_source = urlparse(validated_query.source)
        domain_source = parsed_source.netloc.lower() if parsed_source.netloc else validated_query.source.lower()
        domain_source = domain_source.replace('www.', '')
        logger.debug(f"Normalized source domain: {domain_source}")

        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
        )
        logger.debug(
            f"GNews Configuration - Language: {language}, Country: {country}, "
            f"Max Results: {max_results}, Exclude Duplicates: {exclude_duplicates}"
        )

        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(None, gnews.get_news, domain_source)
        logger.debug(f"Number of articles fetched: {len(articles)}")
        if not articles:
            logger.warning("No articles found for the given parameters.")
            raise HTTPException(status_code=404, detail="No articles found for the given parameters.")

        # Decode URLs asynchronously and filter articles by source
        tasks = []
        for article in articles:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        filtered_articles = []
        for article, decoded_url_response in zip(articles, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Check if the decoded URL matches the source domain
                article_domain = urlparse(decoded_url_response["decoded_url"]).netloc.lower()
                article_domain = article_domain.replace('www.', '')
                if domain_source in article_domain:
                    filtered_articles.append(article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        if not filtered_articles:
            logger.warning(f"No articles found from source '{domain_source}'.")
            raise HTTPException(
                status_code=404,
                detail=f"No articles found from source '{domain_source}'."
            )

        return filtered_articles

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error fetching Google News for source '{source}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/articles/", summary="Get Google News Articles in Bulk")
async def get_google_news_articles(
    query: str = Query("news", description="Search query for the news articles."),
    country: str = Query("US", description="Country for the news results."),
    language: str = Query("en", description="Language for the news results."),
    period: str = Query("1d", description="Period for the news results (e.g., '7d' for last 7 days)."),
    max_results: int = Query(5, description="Maximum number of articles to fetch."),
):
    """
    Get multiple Google News articles over a period based on a search query.
    """
    try:
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            period=period,
        )

        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(None, gnews.get_news, query)
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found for the given parameters.")

        # Decode URLs asynchronously
        tasks = []
        for article in articles:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        for article, decoded_url_response in zip(articles, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return articles
    except Exception as e:
        logger.error(f"Error fetching Google News articles: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/google-news/article-details/", summary="Get Article Details")
async def get_article_details(url: str):
    """
    Get detailed information about a specific article.
    """
    logger.info(f"Received request to get article details for URL: {url}")
    try:
        proxy_url = await get_proxy()  # Adjust if needed

        config = Config()
        if proxy_url:
            logger.debug(f"Using proxy settings for requests: {proxy_url}")
            # Newspaper3k doesn't support the same concept of "mounts"
            # but you can set config.proxies = {"http": "...", "https": "..."} if needed
            config.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
        else:
            logger.debug("No proxy is being used.")

        article = Article(url, config=config)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, article.download)
        await loop.run_in_executor(None, article.parse)

        try:
            await loop.run_in_executor(None, article.nlp)
        except LookupError as e:
            logger.warning(f"NLTK resource not found: {str(e)}")
            return {
                "title": article.title,
                "authors": article.authors,
                "publish_date": article.publish_date,
                "text": article.text,
                "top_image": article.top_image,
                "images": list(article.images),
                "videos": article.movies,
                "meta_data": article.meta_data,
                "meta_description": article.meta_description,
                "meta_keywords": article.meta_keywords,
                "error": "Unable to perform NLP analysis due to missing NLTK resource."
            }

        return {
            "title": article.title,
            "authors": article.authors,
            "publish_date": article.publish_date,
            "text": article.text,
            "summary": article.summary,
            "keywords": article.keywords,
            "top_image": article.top_image,
            "images": list(article.images),
            "videos": article.movies,
            "meta_data": article.meta_data,
            "meta_description": article.meta_description,
            "meta_keywords": article.meta_keywords
        }
    except Exception as e:
        logger.error(f"Error fetching article details for URL '{url}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
