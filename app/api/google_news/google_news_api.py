from fastapi import APIRouter, HTTPException, Query, Depends  # Ensure Depends is imported if not already
from fastapi.responses import JSONResponse
from gnews import GNews
from newspaper import Article, Config
from typing import List, Optional  # Ensure Optional is imported
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
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0],"{base64_str}",{timestamp},"{signature}"]',
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

@gnews_router.get(
    "/available-languages/",
    summary="Get Available Languages",
    response_description="List of available languages for Google News.",
    response_model=dict
)
async def get_languages():
    """
    Get a list of available languages for Google News.
    """
    return {"available_languages": AVAILABLE_LANGUAGES}

@gnews_router.get(
    "/available-countries/",
    summary="Get Available Countries",
    response_description="List of available countries for Google News.",
    response_model=dict
)
async def get_available_countries():
    """
    Get a list of available countries for Google News.
    """
    return {"available_countries": AVAILABLE_COUNTRIES}

@gnews_router.get(
    "/source/",
    summary="Get Google News by Source",
    response_description="List of news articles from a specific source.",
    response_model=NewsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid source URL or domain."},
        404: {"model": ErrorResponse, "description": "No articles found for the given parameters."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_news_by_source(
    source: str = Query(..., description="Source domain or full URL (e.g., 'cnn.com' or 'https://www.cnn.com')"),
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, ge=1, le=100, description="Maximum number of news results (1-100)."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date in YYYY-MM-DD format."),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date in YYYY-MM-DD format."),
):
    """
    Get Google News articles based on a specific source with optional date filtering.

    ### Parameters:
    - **source**: Source domain or full URL (e.g., 'cnn.com' or 'https://www.cnn.com')
    - **language**: Language for the news results (default: 'en')
    - **country**: Country for the news results (default: 'US')
    - **max_results**: Maximum number of news results (1-100)
    - **exclude_duplicates**: Exclude duplicate news articles (default: False)
    - **start_date**: Start date in YYYY-MM-DD format (optional)
    - **end_date**: End date in YYYY-MM-DD format (optional)

    ### Responses:
    - **200 OK**: Returns a list of news articles from the specified source.
    - **400 Bad Request**: Invalid source URL or domain.
    - **404 Not Found**: No articles found for the given parameters.
    - **500 Internal Server Error**: Unexpected server error.
    """
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
                # Transform the article data
                transformed_article = transform_article(article)
                # Check if the decoded URL matches the source domain
                article_domain = urlparse(transformed_article["url"]).netloc.lower()
                article_domain = article_domain.replace('www.', '').strip()
                if domain_source in article_domain:
                    filtered_articles.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        if not filtered_articles:
            raise HTTPException(
                status_code=404,
                detail=f"No articles found from source '{domain_source}' with the given date range."
            )

        return {"articles": filtered_articles}

    except ValidationError as ve:
        logger.error(f"Validation error for source '{source}': {ve}")
        raise HTTPException(status_code=400, detail="Invalid source URL or domain.")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error fetching Google News for source '{source}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/search/",
    summary="Search Google News",
    response_description="List of news articles based on the search query.",
    response_model=NewsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
        404: {"model": ErrorResponse, "description": "No news found for the given query."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def search_google_news(
    query: str = Query(..., description="The search query string."),
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, ge=1, le=100, description="Maximum number of news results (1-100)."),
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date in YYYY-MM-DD format."),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date in YYYY-MM-DD format."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
    exact_match: bool = Query(False, description="Search for an exact match of the query."),
    sort_by: str = Query("relevance", regex="^(relevance|date)$", description="Sort news by 'relevance' or 'date'."),
):
    """
    Search Google News articles based on a query string.

    ### Parameters:
    - **query**: The search query string.
    - **language**: Language for the news results (default: 'en').
    - **country**: Country for the news results (default: 'US').
    - **max_results**: Maximum number of news results (1-100).
    - **start_date**: Start date in YYYY-MM-DD format (optional).
    - **end_date**: End date in YYYY-MM-DD format (optional).
    - **exclude_duplicates**: Exclude duplicate news articles (default: False).
    - **exact_match**: Search for an exact match of the query (default: False).
    - **sort_by**: Sort news by 'relevance' or 'date' (default: 'relevance').

    ### Responses:
    - **200 OK**: Returns a list of news articles based on the search query.
    - **400 Bad Request**: Invalid query parameters.
    - **404 Not Found**: No news found for the given query.
    - **500 Internal Server Error**: Unexpected server error.
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

        processed_news = []
        for article, decoded_url_response in zip(news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Transform the article data
                transformed_article = transform_article(article)
                processed_news.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return {"articles": processed_news}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/top/",
    summary="Get Top Google News",
    response_description="List of top news articles.",
    response_model=NewsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No top news found."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_top_google_news(
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(10, ge=1, le=100, description="Maximum number of news results (1-100)."),
):
    """
    Get the top Google News articles.

    ### Parameters:
    - **language**: Language for the news results (default: 'en').
    - **country**: Country for the news results (default: 'US').
    - **max_results**: Maximum number of news results (1-100).

    ### Responses:
    - **200 OK**: Returns a list of top news articles.
    - **404 Not Found**: No top news found.
    - **500 Internal Server Error**: Unexpected server error.
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

        processed_top_news = []
        for article, decoded_url_response in zip(top_news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Transform the article data
                transformed_article = transform_article(article)
                processed_top_news.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return {"articles": processed_top_news}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching top Google News: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/topic/",
    summary="Get Google News by Topic",
    response_description="List of news articles based on the specified topic.",
    response_model=NewsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid topic provided."},
        404: {"model": ErrorResponse, "description": "No news found for the given topic."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_news_by_topic(
    topic: str = Query(..., description="The topic to filter news articles."),
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, ge=1, le=100, description="Maximum number of news results (1-100)."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
):
    """
    Get Google News articles based on a specific topic.
    
    ### Parameters:
    - **topic**: The topic to filter news articles.
    - **language**: Language for the news results (default: 'en').
    - **country**: Country for the news results (default: 'US').
    - **max_results**: Maximum number of news results (1-100).
    - **exclude_duplicates**: Exclude duplicate news articles (default: False).
    
    ### Responses:
    - **200 OK**: Returns a list of news articles based on the specified topic.
    - **400 Bad Request**: Invalid topic provided.
    - **404 Not Found**: No news found for the given topic.
    - **500 Internal Server Error**: Unexpected server error.
    """
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

        # Decode URLs asynchronously
        tasks = []
        for article in news:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        processed_news = []
        for article, decoded_url_response in zip(news, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Transform the article data
                transformed_article = transform_article(article)
                processed_news.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return {"articles": processed_news}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for topic '{topic}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/location/",
    summary="Get Google News by Location",
    response_description="List of news articles based on a specific location.",
    response_model=NewsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No news found for the given location."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_news_by_location(
    location: str = Query(..., description="The location to filter news articles."),
    language: str = Query("en", description="Language for the news results."),
    country: str = Query("US", description="Country for the news results."),
    max_results: int = Query(5, ge=1, le=100, description="Maximum number of news results (1-100)."),
    start_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="Start date in YYYY-MM-DD format."),
    end_date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", description="End date in YYYY-MM-DD format."),
    exclude_duplicates: bool = Query(False, description="Exclude duplicate news articles."),
):
    """
    Get Google News articles based on a specific location.

    ### Parameters:
    - **location**: The location to filter news articles.
    - **language**: Language for the news results (default: 'en').
    - **country**: Country for the news results (default: 'US').
    - **max_results**: Maximum number of news results (1-100).
    - **start_date**: Start date in YYYY-MM-DD format (optional).
    - **end_date**: End date in YYYY-MM-DD format (optional).
    - **exclude_duplicates**: Exclude duplicate news articles (default: False).

    ### Responses:
    - **200 OK**: Returns a list of news articles based on the specified location.
    - **404 Not Found**: No news found for the given location.
    - **500 Internal Server Error**: Unexpected server error.
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

        processed_news = []
        for article, decoded_url_response in zip(news_by_location, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Transform the article data
                transformed_article = transform_article(article)
                processed_news.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return {"articles": processed_news}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for location '{location}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# The `/source/` endpoint definition is already provided above.

@gnews_router.get(
    "/articles/",
    summary="Get Google News Articles in Bulk",
    response_description="Bulk list of Google News articles based on a search query and period.",
    response_model=NewsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No articles found for the given parameters."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_google_news_articles(
    query: str = Query("news", description="Search query for the news articles."),
    country: str = Query("US", description="Country for the news results."),
    language: str = Query("en", description="Language for the news results."),
    period: str = Query("1d", regex=r"^\d+[dwmy]$", description="Period for the news results (e.g., '7d' for last 7 days)."),
    max_results: int = Query(5, ge=1, le=100, description="Maximum number of articles to fetch (1-100)."),
):
    """
    Get multiple Google News articles over a period based on a search query.

    ### Parameters:
    - **query**: Search query for the news articles (default: 'news').
    - **country**: Country for the news results (default: 'US').
    - **language**: Language for the news results (default: 'en').
    - **period**: Period for the news results (e.g., '7d' for last 7 days).
    - **max_results**: Maximum number of articles to fetch (1-100).

    ### Responses:
    - **200 OK**: Returns a bulk list of news articles based on the search query and period.
    - **404 Not Found**: No articles found for the given parameters.
    - **500 Internal Server Error**: Unexpected server error.
    """
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

        # Decode URLs asynchronously
        tasks = []
        for article in articles:
            source_url = article.get('url')
            tasks.append(decode_google_news_url(source_url))
        decoded_results = await asyncio.gather(*tasks)

        processed_articles = []
        for article, decoded_url_response in zip(articles, decoded_results):
            if decoded_url_response.get("status"):
                article['url'] = decoded_url_response["decoded_url"]
                # Transform the article data
                transformed_article = transform_article(article)
                processed_articles.append(transformed_article)
            else:
                logger.warning(
                    f"Could not decode URL for article '{article.get('title', 'N/A')}': "
                    f"{decoded_url_response.get('message')}"
                )

        return {"articles": processed_articles}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News articles for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/article-details/",
    summary="Get Article Details",
    response_description="Detailed information about a specific article.",
    response_model=dict,
    responses={
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_article_details(
    url: str = Query(..., description="URL of the article to retrieve details for.")
):
    """
    Get detailed information about a specific article.

    ### Parameters:
    - **url**: URL of the article to retrieve details for.

    ### Responses:
    - **200 OK**: Returns detailed information about the specified article.
    - **500 Internal Server Error**: Unexpected server error.
    """
    logger.info(f"Received request to get article details for URL: {url}")
    try:
        proxy_url = await get_proxy()  # Adjust if needed

        config = Config()
        if proxy_url:
            logger.debug(f"Using proxy settings for requests: {proxy_url}")
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
