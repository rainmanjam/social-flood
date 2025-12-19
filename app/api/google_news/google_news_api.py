from fastapi import APIRouter, HTTPException, Query, Depends, Request  # Ensure Depends is imported if not already
from fastapi.responses import JSONResponse
from gnews import GNews
from newspaper import Article, Config, ArticleException
from typing import List, Optional  # Ensure Optional is imported
import logging
import json
import asyncio
from urllib.parse import quote, urlparse
import httpx
from selectolax.parser import HTMLParser
import os
import nltk
from pydantic import BaseModel, validator, ValidationError
import re
from app.core.proxy import get_proxy  # adjust if needed
import datetime
from app.core.rate_limiter import rate_limit
from app.core.cache_manager import cache_manager, generate_cache_key, get_cached_or_fetch
from app.core.config import get_settings
from app.core.http_client import get_http_client_manager
from app.core.constants import USER_AGENTS

# Initialize NLTK asynchronously at module level
async def setup_nltk():
    """Setup NLTK resources once at startup."""
    try:
        # Set NLTK data path to a writable directory
        nltk_data_dir = os.path.join(os.getcwd(), "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        nltk.data.path.insert(0, nltk_data_dir)
        
        # Check if 'punkt_tab' is already downloaded
        try:
            nltk.data.find('tokenizers/punkt_tab')
            logger.info("NLTK 'punkt_tab' resource already available.")
        except LookupError:
            # 'punkt_tab' not found, so download it
            logger.info("NLTK 'punkt_tab' resource not found. Downloading...")
            nltk.download('punkt_tab', nltk_data_dir, quiet=True)
            logger.info("NLTK 'punkt_tab' resource downloaded successfully.")
            
        # Also download 'punkt' as fallback
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            logger.info("Downloading fallback 'punkt' resource...")
            nltk.download('punkt', nltk_data_dir, quiet=True)
            
    except Exception as e:
        # Handle any other exceptions during NLTK setup
        logger.error(f"An error occurred during NLTK setup: {e}")

# Run NLTK setup at import time (this will be awaited in the lifespan event)
_nltk_setup_task = None

async def ensure_nltk_setup():
    """Ensure NLTK is set up, running setup only once."""
    global _nltk_setup_task
    if _nltk_setup_task is None:
        _nltk_setup_task = asyncio.create_task(setup_nltk())
    await _nltk_setup_task

# Initialize Google News API Router
gnews_router = APIRouter()
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)  # Ensure DEBUG level logs are captured -> This should be handled by the main application entry point

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
    "WORLD", "NATION", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH",
    "POLITICS", "CELEBRITIES", "TV", "MUSIC", "MOVIES", "THEATER", "SOCCER", "CYCLING",
    "MOTOR SPORTS", "TENNIS", "COMBAT SPORTS", "BASKETBALL", "BASEBALL", "FOOTBALL",
    "SPORTS BETTING", "WATER SPORTS", "HOCKEY", "GOLF", "CRICKET", "RUGBY", "ECONOMY",
    "PERSONAL FINANCE", "FINANCE", "DIGITAL CURRENCIES", "MOBILE", "ENERGY", "GAMING",
    "INTERNET SECURITY", "GADGETS", "VIRTUAL REALITY", "ROBOTICS", "NUTRITION", "PUBLIC HEALTH",
    "MENTAL HEALTH", "MEDICINE", "SPACE", "WILDLIFE", "ENVIRONMENT", "NEUROSCIENCE",
    "PHYSICS", "GEOLOGY", "PALEONTOLOGY", "SOCIAL SCIENCES", "EDUCATION", "JOBS",
    "ONLINE EDUCATION", "HIGHER EDUCATION", "VEHICLES", "ARTS-DESIGN", "BEAUTY", "FOOD",
    "TRAVEL", "SHOPPING", "HOME", "OUTDOORS", "FASHION"
]

AVAILABLE_LANGUAGES = {
    'english': 'en',
    'indonesian': 'id',
    'czech': 'cs',
    'german': 'de',
    'spanish': 'es-419',
    'french': 'fr',
    'italian': 'it',
    'latvian': 'lv',
    'lithuanian': 'lt',
    'hungarian': 'hu',
    'dutch': 'nl',
    'norwegian': 'no',
    'polish': 'pl',
    'portuguese brasil': 'pt-419',
    'portuguese portugal': 'pt-150',
    'romanian': 'ro',
    'slovak': 'sk',
    'slovenian': 'sl',
    'swedish': 'sv',
    'vietnamese': 'vi',
    'turkish': 'tr',
    'greek': 'el',
    'bulgarian': 'bg',
    'russian': 'ru',
    'serbian': 'sr',
    'ukrainian': 'uk',
    'hebrew': 'he',
    'arabic': 'ar',
    'marathi': 'mr',
    'hindi': 'hi',
    'bengali': 'bn',
    'tamil': 'ta',
    'telugu': 'te',
    'malyalam': 'ml',
    'thai': 'th',
    'chinese simplified': 'zh-Hans',
    'chinese traditional': 'zh-Hant',
    'japanese': 'ja',
    'korean': 'ko'
}

AVAILABLE_COUNTRIES = {
    'Australia': 'AU',
    'Botswana': 'BW',
    'Canada': 'CA',
    'Ethiopia': 'ET',
    'Ghana': 'GH',
    'India': 'IN',
    'Indonesia': 'ID',
    'Ireland': 'IE',
    'Israel': 'IL',
    'Kenya': 'KE',
    'Latvia': 'LV',
    'Malaysia': 'MY',
    'Namibia': 'NA',
    'New Zealand': 'NZ',
    'Nigeria': 'NG',
    'Pakistan': 'PK',
    'Philippines': 'PH',
    'Singapore': 'SG',
    'South Africa': 'ZA',
    'Tanzania': 'TZ',
    'Uganda': 'UG',
    'United Kingdom': 'GB',
    'United States': 'US',
    'Zimbabwe': 'ZW',
    'Czech Republic': 'CZ',
    'Germany': 'DE',
    'Austria': 'AT',
    'Switzerland': 'CH',
    'Argentina': 'AR',
    'Chile': 'CL',
    'Colombia': 'CO',
    'Cuba': 'CU',
    'Mexico': 'MX',
    'Peru': 'PE',
    'Venezuela': 'VE',
    'Belgium': 'BE',
    'France': 'FR',
    'Morocco': 'MA',
    'Senegal': 'SN',
    'Italy': 'IT',
    'Lithuania': 'LT',
    'Hungary': 'HU',
    'Netherlands': 'NL',
    'Norway': 'NO',
    'Poland': 'PL',
    'Brazil': 'BR',
    'Portugal': 'PT',
    'Romania': 'RO',
    'Slovakia': 'SK',
    'Slovenia': 'SI',
    'Sweden': 'SE',
    'Vietnam': 'VN',
    'Turkey': 'TR',
    'Greece': 'GR',
    'Bulgaria': 'BG',
    'Russia': 'RU',
    'Ukraine': 'UA',
    'Serbia': 'RS',
    'United Arab Emirates': 'AE',
    'Saudi Arabia': 'SA',
    'Lebanon': 'LB',
    'Egypt': 'EG',
    'Bangladesh': 'BD',
    'Thailand': 'TH',
    'China': 'CN',
    'Taiwan': 'TW',
    'Hong Kong': 'HK',
    'Japan': 'JP',
    'Republic of Korea': 'KR'
}

# Global cache manager instance
settings = get_settings()


# Use centralized HTTP client manager for GNews operations
async def get_gnews_http_client(proxy_url: Optional[str] = None) -> httpx.AsyncClient:
    """
    Get a shared HTTP client for GNews operations using centralized HTTPClientManager.

    Args:
        proxy_url: Optional proxy URL

    Returns:
        httpx.AsyncClient: Shared HTTP client from connection pool
    """
    http_manager = get_http_client_manager()
    return await http_manager.get_client(proxy_url)

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

        client = await get_gnews_http_client(proxy_url=proxy_url)
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
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0],"{base64_str}",{timestamp},"{signature}"]',
        ]
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": USER_AGENTS["windows_chrome"],
        }

        proxy_url = await get_proxy()  # Adjust based on your implementation

        client = await get_gnews_http_client(proxy_url=proxy_url)
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
    proxy_url_val = await get_proxy()

    # Initialize GNews with proxy for its internal feedparser usage
    gnews = GNews(
        language=language,
        country=country,
        max_results=max_results,
        period=period,
        start_date=start_date,
        end_date=end_date,
        # exclude_websites can be set if needed, GNews constructor supports it
        proxy=proxy_url_val  # Pass the proxy URL to GNews constructor
    )

    # Set attributes not available in constructor or that need to be dynamically set
    gnews.exclude_duplicates = exclude_duplicates
    gnews.exact_match = exact_match
    gnews.sort_by = sort_by
    # Period, start_date, end_date are already set via constructor if provided

    # Set up httpx.AsyncClient on gnews.session for any parts of GNews that might use it
    # (or for future use/consistency, as the original code did this).
    if proxy_url_val:
        mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=proxy_url_val),
            "https://": httpx.AsyncHTTPTransport(proxy=proxy_url_val),
        }
        gnews.session = httpx.AsyncClient(mounts=mounts)
        logger.debug(f"GNews instance using proxy for httpx session: {proxy_url_val}")
        if proxy_url_val: # Logging for clarity that proxy is also set for feedparser
            logger.debug(f"GNews instance also configured with proxy for feedparser: {proxy_url_val}")
    else:
        gnews.session = httpx.AsyncClient()
        logger.debug("GNews instance not using any proxy for httpx session or feedparser.")

    return gnews

# -----------------------------------------------------------------------------
# Helper: Decode and Process Articles (Concurrent Version)
# -----------------------------------------------------------------------------
async def decode_and_process_articles(
    raw_articles: List[dict],
    filter_by_domain: Optional[str] = None,
    max_concurrent: int = 10
) -> List[dict]:
    """
    Decodes Google News URLs for a list of articles and processes them concurrently.
    Optionally filters articles by a specified domain.
    
    Args:
        raw_articles: List of raw article dictionaries
        filter_by_domain: Optional domain to filter by
        max_concurrent: Maximum number of concurrent decoding operations
        
    Returns:
        List of processed articles
    """
    if not raw_articles:
        return []

    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def decode_single_article(article_data: dict) -> Optional[dict]:
        """Decode and process a single article with semaphore control."""
        async with semaphore:
            if not article_data.get('url'):
                return None
            
            try:
                # Decode URL
                decoded_result = await decode_google_news_url(article_data.get('url'))
                
                if decoded_result.get("status"):
                    article_data['url'] = decoded_result["decoded_url"]
                    transformed_article = transform_article(article_data)
                    
                    # Apply domain filtering if specified
                    if filter_by_domain:
                        article_domain = urlparse(transformed_article["url"]).netloc.lower().replace('www.', '').strip()
                        if filter_by_domain not in article_domain:
                            logger.debug(f"Skipping article '{transformed_article['title']}' as its domain '{article_domain}' does not match '{filter_by_domain}'")
                            return None
                    
                    return transformed_article
                else:
                    logger.warning(
                        f"Could not decode URL for article '{article_data.get('title', 'N/A')}': "
                        f"{decoded_result.get('message')}"
                    )
                    return None
            except Exception as e:
                logger.warning(
                    f"Exception during URL decoding for article '{article_data.get('title', 'N/A')}': {e}"
                )
                return None

    # Process all articles concurrently
    tasks = [decode_single_article(article) for article in raw_articles]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None results and exceptions
    processed_articles = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Unexpected error in concurrent processing: {result}")
            continue
        if result is not None:
            processed_articles.append(result)
    
    logger.debug(f"Successfully processed {len(processed_articles)} out of {len(raw_articles)} articles")
    return processed_articles

# -----------------------------------------------------------------------------
# Pydantic Models for Responses
# -----------------------------------------------------------------------------
class NewsArticle(BaseModel):
    title: str
    published_date: str
    description: Optional[str]
    url: str
    publisher: Optional[str]

class NewsResponse(BaseModel):
    articles: List[NewsArticle]

class ErrorResponse(BaseModel):
    detail: str

# -----------------------------------------------------------------------------
# Helper: Transform Article Data
# -----------------------------------------------------------------------------
def transform_article(article: dict) -> dict:
    return {
        "title": article.get("title"),
        "description": article.get("description"),
        "published_date": article.get("published date"),
        "url": article.get("url"),
        "publisher": article.get("publisher", {}).get("title") if article.get("publisher") else None
    }

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@gnews_router.get("/available-languages/", summary="Available Languages", response_model=dict)
async def get_languages():
    """Get supported languages for Google News."""
    return {"available_languages": AVAILABLE_LANGUAGES}

@gnews_router.get("/available-countries/", summary="Available Countries", response_model=dict)
async def get_available_countries():
    """Get supported countries for Google News."""
    return {"available_countries": AVAILABLE_COUNTRIES}

@gnews_router.get("/source/", summary="News by Source", response_model=NewsResponse)
async def get_news_by_source(
    # === REQUIRED ===
    source: str = Query(..., description="Source domain or URL", example="cnn.com"),
    # === COMMONLY USED ===
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(5, ge=1, le=100, description="Max results (1-100)"),
    # === DATE FILTERS ===
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)"),
    # === OPTIONS ===
    exclude_duplicates: bool = Query(False, description="Exclude duplicates"),
):
    """Get news articles from a specific source."""
    try:
        # Validate input using SourceQuery
        validated_query = SourceQuery(source=source)

        # Normalize the source input by extracting the domain if a URL is provided
        parsed_source = urlparse(validated_query.source)
        domain_source = parsed_source.netloc.lower() if parsed_source.netloc else validated_query.source.lower()
        domain_source = domain_source.replace('www.', '').strip()

        # Parse dates if provided
        start_date_tuple = tuple(map(int, start_date.split("-"))) if start_date else None
        end_date_tuple = tuple(map(int, end_date.split("-"))) if end_date else None

        # Create a new GNews instance with start_date and end_date
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
            start_date=start_date_tuple,
            end_date=end_date_tuple,
        )

        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(None, gnews.get_news, domain_source)
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found for the given parameters.")

        # Use the new helper function to decode URLs and filter
        processed_articles = await decode_and_process_articles(articles, filter_by_domain=domain_source)

        if not processed_articles:
            raise HTTPException(
                status_code=404,
                detail=f"No articles found from source '{domain_source}' with the given date range."
            )

        return {"articles": processed_articles}

    except ValidationError as ve:
        logger.error(f"Validation error for source '{source}': {ve}")
        raise HTTPException(status_code=400, detail="Invalid source URL or domain.")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error fetching Google News for source '{source}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/search/", summary="Search News", response_model=NewsResponse)
async def search_google_news(
    request: Request,
    # === REQUIRED ===
    query: str = Query(..., description="Search query", example="climate change"),
    # === COMMONLY USED ===
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(5, ge=1, le=100, description="Max results (1-100)"),
    sort_by: str = Query("relevance", regex="^(relevance|date)$", description="Sort by: relevance, date"),
    # === DATE FILTERS ===
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)"),
    # === OPTIONS ===
    exclude_duplicates: bool = Query(False, description="Exclude duplicates"),
    exact_match: bool = Query(False, description="Exact match only"),
    # === AUTH ===
    rate_limit_check: None = Depends(rate_limit),
):
    """Search news articles by query."""
    try:
        # Parse dates if provided
        start_date_tuple = tuple(map(int, start_date.split("-"))) if start_date else None
        end_date_tuple = tuple(map(int, end_date.split("-"))) if end_date else None

        # Generate cache key
        cache_key = generate_cache_key(
            "gnews:search",
            query=query,
            language=language,
            country=country,
            max_results=max_results,
            start_date=start_date,
            end_date=end_date,
            exclude_duplicates=exclude_duplicates,
            exact_match=exact_match,
            sort_by=sort_by
        )

        async def fetch_search_results():
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

            # Use the new helper function to decode URLs
            processed_articles = await decode_and_process_articles(news)
            
            if not processed_articles: # Check if processing yielded any articles
                # This condition might be hit if all URLs failed to decode or were filtered out
                # Depending on desired behavior, could raise 404 or return empty list
                # For now, let's assume if news was found initially but processing failed for all, it's still a "not found" scenario for valid articles.
                raise HTTPException(status_code=404, detail="No processable news found after URL decoding.")

            return {"articles": processed_articles}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_search_results)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/top/", summary="Top News", response_model=NewsResponse)
async def get_top_google_news(
    # === COMMONLY USED ===
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(10, ge=1, le=100, description="Max results (1-100)"),
):
    """Get top news articles."""
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

        # Use the new helper function to decode URLs
        processed_articles = await decode_and_process_articles(top_news)

        if not processed_articles: # Similar check as in /search
            raise HTTPException(status_code=404, detail="No processable top news found after URL decoding.")
            
        return {"articles": processed_articles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching top Google News: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/topic/", summary="News by Topic", response_model=NewsResponse)
async def get_news_by_topic(
    # === REQUIRED ===
    topic: str = Query(..., description="Topic name (WORLD, TECHNOLOGY, SPORTS, etc.)", example="TECHNOLOGY"),
    # === COMMONLY USED ===
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(5, ge=1, le=100, description="Max results (1-100)"),
    # === OPTIONS ===
    exclude_duplicates: bool = Query(False, description="Exclude duplicates"),
):
    """Get news articles by topic."""
    if topic.upper() not in AVAILABLE_TOPICS:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid topic provided.", "available_topics": AVAILABLE_TOPICS}
        )
    try:
        # Create a new GNews instance without start_date and end_date
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=exclude_duplicates,
        )

        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, gnews.get_news_by_topic, topic)

        if not news:
            raise HTTPException(status_code=404, detail="No news found for the given topic.")

        # Use the new helper function to decode URLs
        processed_articles = await decode_and_process_articles(news)

        if not processed_articles: # Similar check
            raise HTTPException(status_code=404, detail="No processable news found for the topic after URL decoding.")

        return {"articles": processed_articles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for topic '{topic}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/location/", summary="News by Location", response_model=NewsResponse)
async def get_news_by_location(
    # === REQUIRED ===
    location: str = Query(..., description="Location name", example="New York"),
    # === COMMONLY USED ===
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(5, ge=1, le=100, description="Max results (1-100)"),
    # === DATE FILTERS ===
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)"),
    # === OPTIONS ===
    exclude_duplicates: bool = Query(False, description="Exclude duplicates"),
):
    """Get news articles by location."""
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

        # Use the new helper function to decode URLs
        processed_articles = await decode_and_process_articles(news_by_location)

        if not processed_articles: # Similar check
            raise HTTPException(status_code=404, detail=f"No processable news found for the location '{location}' after URL decoding.")
            
        return {"articles": processed_articles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for location '{location}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# The `/source/` endpoint definition is already provided above.

@gnews_router.get("/articles/", summary="Bulk Articles", response_model=NewsResponse)
async def get_google_news_articles(
    # === COMMONLY USED ===
    query: str = Query("news", description="Search query", example="technology"),
    language: str = Query("en", description="Language code", example="en"),
    country: str = Query("US", description="Country code", example="US"),
    max_results: int = Query(5, ge=1, le=100, description="Max results (1-100)"),
    # === TIME PERIOD ===
    period: str = Query("1d", regex=r"^\d+[dwmy]$", description="Period: 7d, 1w, 1m, 1y"),
):
    """Get bulk news articles over a time period."""
    try:
        # Create a new GNews instance
        gnews = await get_gnews_instance(
            language=language,
            country=country,
            max_results=max_results,
            exclude_duplicates=False,
        )

        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(None, gnews.get_news, query)
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found for the given parameters.")

        # Use the new helper function to decode URLs
        processed_articles = await decode_and_process_articles(articles)
        
        if not processed_articles: # Similar check
            raise HTTPException(status_code=404, detail="No processable articles found for the given parameters after URL decoding.")

        return {"articles": processed_articles}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News articles for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get("/article-details/", summary="Article Details", response_model=dict)
async def get_article_details(
    # === REQUIRED ===
    url: str = Query(..., description="Article URL to analyze"),
):
    """Get detailed article information (title, text, summary, keywords)."""
    logger.info(f"Received request to get article details for URL: {url}")
    try:
        # Ensure NLTK is set up (only runs once)
        await ensure_nltk_setup()
        
        proxy_url = await get_proxy()  # Adjust if needed

        config = Config()
        config.request_timeout = settings.HTTP_READ_TIMEOUT  # Use configured timeout
        config.thread_timeout = settings.HTTP_READ_TIMEOUT
        if proxy_url:
            logger.debug(f"Using proxy settings for requests: {proxy_url}")
            config.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
        else:
            logger.debug("No proxy is being used.")

        # Use asyncio to run newspaper operations
        loop = asyncio.get_event_loop()
        
        # Download article
        article = Article(url, config=config)
        await loop.run_in_executor(None, article.download)
        
        # Parse article
        await loop.run_in_executor(None, article.parse)

        # Try NLP processing
        nlp_success = True
        try:
            await loop.run_in_executor(None, article.nlp)
        except LookupError as le: # Specific exception for NLTK resource not found
            logger.warning(f"NLTK resource not found for URL '{url}': {str(le)}")
            nlp_success = False

        # Build response
        response_data = {
            "title": article.title,
            "authors": article.authors,
            "publish_date": article.publish_date,
            "text": article.text,
            "top_image": article.top_image,
            "images": list(article.images),
            "videos": article.movies,
            "meta_data": article.meta_data,
            "meta_description": article.meta_description,
            "meta_keywords": article.meta_keywords
        }
        
        if nlp_success:
            response_data.update({
                "summary": article.summary,
                "keywords": article.keywords
            })
        else:
            response_data["error"] = "Unable to perform NLP analysis due to missing NLTK resource."

        return response_data
        
    except ArticleException as ae:
        logger.error(f"Newspaper library error for URL '{url}': {str(ae)}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: Could not process article from URL. Error: {str(ae)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching article details for URL '{url}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
