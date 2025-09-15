# google_trends_api.py

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import date
import logging
import asyncio
import pandas as pd
import numpy as np
from enum import IntEnum, Enum
from typing import List, Optional, Union
from trendspy import Trends, BatchPeriod
from app.core.proxy import get_proxy
from app.core.cache_manager import generate_cache_key, get_cached_or_fetch
from app.core.rate_limiter import rate_limit
from app.core.http_client import http_manager
import random
import json

# Add TimeframeEnum
class TimeframeEnum(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5

# Add HumanFriendlyBatchPeriod Enum
class HumanFriendlyBatchPeriod(str, Enum):
    past_4h = "past_4h"
    past_24h = "past_24h"
    past_48h = "past_48h"
    past_7d = "past_7d"

# Define Enums for each time format
class StandardTimeframe(str, Enum):
    NOW_1H = "now 1-H"
    NOW_4H = "now 4-H"
    TODAY_1M = "today 1-m"
    TODAY_3M = "today 3-m"
    TODAY_12M = "today 12-m"

class CustomIntervalTimeframe(str, Enum):
    NOW_123H = "now 123-H"
    NOW_72H = "now 72-H"
    TODAY_45D = "today 45-d"
    TODAY_90D = "today 90-d"
    TODAY_18M = "today 18-m"

# Pydantic model for date range
class DateRangeTimeframeModel(BaseModel):
    start_date: date = Field(..., description="Start date in YYYY-MM-DD format.")
    end_date: Optional[date] = Field(None, description="End date in YYYY-MM-DD format.")

# Create the router
google_trends_router = APIRouter()
logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.DEBUG)

# -------------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------------
def df_to_json(df: pd.DataFrame):
    """
    Convert a Pandas DataFrame to a list of dictionaries.
    If df is empty, return an empty list.
    """
    if df.empty:
        return []
    return df.reset_index(drop=True).to_dict(orient='records')

def to_jsonable(value):
    """
    Recursively convert objects to JSON-serializable types:
    - Pandas DataFrames -> list of dicts
    - Numpy int/float  -> Python int/float
    - Numpy arrays     -> lists
    - dict/list        -> recursively process
    """
    if isinstance(value, pd.DataFrame):
        return df_to_json(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(x) for x in value]
    return value

# -------------------------------------------------------------------------
# Header Configuration
# -------------------------------------------------------------------------
REFERER_LIST = [
    "https://www.google.com/",
    "https://news.google.com/",
    "https://www.bing.com/",
    "https://www.yahoo.com/",
    "https://www.duckduckgo.com/",
    "https://www.ask.com/",
    "https://www.aol.com/",
    "https://www.ecosia.org/",
    "https://www.startpage.com/",
    "https://www.qwant.com/"
]

USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 10; Mobile; rv:79.0)",
    "Mozilla/5.0 (Windows NT 6.1; WOW64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0)",
    "Mozilla/5.0 (iPod touch; CPU iPhone OS 14_0 like Mac OS X)"
]

def get_random_headers():
    """
    Selects a random referer and user-agent from predefined lists.
    Returns a dictionary of headers.
    """
    referer = random.choice(REFERER_LIST)
    user_agent = random.choice(USER_AGENT_LIST)
    headers = {
        "Referer": referer,
        "User-Agent": user_agent,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    return headers

# -------------------------------------------------------------------------
# Helper: Create a new Trends instance per request
# -------------------------------------------------------------------------
async def get_trends_instance():
    """
    Create and return a Trends instance, applying proxy if needed and random headers.
    """
    proxy_url = await get_proxy()
    headers = get_random_headers()
    if proxy_url:
        logger.debug(f"TrendSpy is using proxy: {proxy_url}")
        return Trends(proxy=proxy_url, headers=headers)
    else:
        logger.debug("TrendSpy is not using any proxy.")
        return Trends(headers=headers)

# -------------------------------------------------------------------------
# 1) Interest Over Time
# -------------------------------------------------------------------------
@google_trends_router.get("/interest-over-time", summary="Google Trends: Interest Over Time")
async def interest_over_time(
    keywords: str = Query(..., description="Comma-separated keywords (e.g., 'python,javascript')"),
    timeframe: str = Query("today 12-m", description="Timeframe for the query (e.g., 'now 4-H', 'today 3-m')."),
    geo: Optional[str] = Query(None, description="Geolocation code (e.g., 'US', 'US-NY')."),
    cat: Optional[str] = Query(None, description="Category ID (e.g., '13' for Computers & Electronics)."),
    gprop: Optional[str] = Query(None, description="Google property (e.g., 'images', 'youtube')."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves Google Trends interest over time for the specified keywords.
    """
    try:
        kw_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        if not kw_list:
            raise HTTPException(status_code=400, detail="No valid keywords provided.")

        # Generate cache key
        cache_key = generate_cache_key(
            "trends_interest_over_time",
            keywords=keywords,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop
        )

        async def fetch_interest_over_time():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_interest_over_time():
                try:
                    logger.debug(f"Calling TrendSpy API with keywords: {kw_list}, timeframe: {timeframe}, geo: {geo}, cat: {cat}, gprop: {gprop}")
                    df = trends_obj.interest_over_time(
                        kw_list,
                        timeframe=timeframe,
                        geo=geo,
                        cat=cat,
                        gprop=gprop
                    )
                    logger.debug(f"Raw API response: {df}")

                    if df is None or df.empty:
                        logger.warning("TrendSpy API returned no data for interest_over_time")
                        return None

                    return df

                except Exception as e:
                    logger.error(f"Error processing interest_over_time data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_interest_over_time)

            if raw_results is None:
                logger.warning("No data returned from TrendSpy API for interest_over_time")
                return {"data": [], "message": "No data returned from Google Trends."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process interest over time data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_interest_over_time)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in interest_over_time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 2) Interest By Region
# -------------------------------------------------------------------------
@google_trends_router.get("/interest-by-region", summary="Google Trends: Interest By Region")
async def interest_by_region(
    keyword: str = Query(..., description="Single keyword (e.g., 'python')."),
    timeframe: str = Query("today 12-m", description="Timeframe."),
    geo: Optional[str] = Query(None, description="Geolocation code."),
    cat: Optional[str] = Query(None, description="Category ID."),
    resolution: str = Query("COUNTRY", description="Resolution level (COUNTRY, REGION, CITY)."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves Google Trends interest by region for the specified keyword.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_interest_by_region",
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            resolution=resolution
        )

        async def fetch_interest_by_region():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_interest_by_region():
                try:
                    logger.debug(f"Calling TrendSpy API with keyword: {keyword}, timeframe: {timeframe}, geo: {geo}, cat: {cat}, resolution: {resolution}")
                    df = trends_obj.interest_by_region(
                        keyword,
                        timeframe=timeframe,
                        geo=geo,
                        cat=cat,
                        resolution=resolution
                    )
                    logger.debug(f"Raw API response: {df}")

                    if df is None or df.empty:
                        logger.warning("TrendSpy API returned no data for interest_by_region")
                        return None

                    return df

                except Exception as e:
                    logger.error(f"Error processing interest_by_region data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_interest_by_region)

            if raw_results is None:
                logger.warning("No data returned from TrendSpy API for interest_by_region")
                return {"data": [], "message": "No data returned from Google Trends."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process interest by region data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_interest_by_region)

    except Exception as e:
        logger.error(f"Error in interest_by_region: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 3) Related Queries (Uses a Custom Referer in the Headers)
# -------------------------------------------------------------------------
@google_trends_router.get("/related-queries", summary="Google Trends: Related Queries")
async def related_queries(
    keyword: str = Query(..., description="Single keyword (e.g., 'python')."),
    timeframe: str = Query("today 12-m", description="Timeframe."),
    geo: Optional[str] = Query(None, description="Geolocation code."),
    cat: Optional[str] = Query(None, description="Category ID."),
    gprop: Optional[str] = Query(None, description="Google property (e.g., 'images', 'youtube')."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves related queries for a specified keyword.
    Adds a custom referer header to help bypass certain rate limits.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_related_queries",
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop
        )

        async def fetch_related_queries():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_related_queries():
                try:
                    logger.debug(f"Calling TrendSpy API with keyword: {keyword}, timeframe: {timeframe}, geo: {geo}, cat: {cat}, gprop: {gprop}")
                    data = trends_obj.related_queries(
                        keyword,
                        timeframe=timeframe,
                        geo=geo,
                        cat=cat,
                        gprop=gprop
                    )
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for related_queries")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing related_queries data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_related_queries)

            if raw_results is None:
                logger.warning("No related queries data returned from TrendSpy API")
                return {"data": [], "message": "No related queries data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process related queries data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_related_queries)

    except Exception as e:
        logger.error(f"Error in related_queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 4) Related Topics
# -------------------------------------------------------------------------
@google_trends_router.get("/related-topics", summary="Google Trends: Related Topics")
async def related_topics(
    keyword: str = Query(..., description="Single keyword."),
    timeframe: str = Query("today 12-m", description="Timeframe."),
    geo: Optional[str] = Query(None, description="Geolocation code."),
    cat: Optional[str] = Query(None, description="Category ID."),
    gprop: Optional[str] = Query(None, description="Google property."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves related topics for a specified keyword.
    Adds a custom Referer header to help bypass certain rate limits.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_related_topics",
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop
        )

        async def fetch_related_topics():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_related_topics():
                try:
                    logger.debug(f"Calling TrendSpy API with keyword: {keyword}, timeframe: {timeframe}, geo: {geo}, cat: {cat}, gprop: {gprop}")
                    data = trends_obj.related_topics(
                        keyword,
                        timeframe=timeframe,
                        geo=geo,
                        cat=cat,
                        gprop=gprop
                    )
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for related_topics")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing related_topics data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_related_topics)

            if raw_results is None:
                logger.warning("No related topics data returned from TrendSpy API")
                return {"data": [], "message": "No related topics data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process related topics data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_related_topics)

    except Exception as e:
        logger.error(f"Error in related_topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 5) Trending Now
# -------------------------------------------------------------------------
@google_trends_router.get("/trending-now", summary="Google Trends: Trending Now")
async def trending_now(
    geo: Optional[str] = Query("US", description="Geolocation code for trending searches (e.g., 'US')."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves current trending searches for the specified geo.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_trending_now",
            geo=geo
        )

        async def fetch_trending_now():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_trending_now():
                try:
                    logger.debug(f"Calling TrendSpy API with geo: {geo}")
                    data = trends_obj.trending_now(geo=geo)
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for trending_now")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing trending_now data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_trending_now)

            if raw_results is None:
                logger.warning("No trending now data returned from TrendSpy API")
                return {"data": [], "message": "No trending now data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process trending now data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_trending_now)

    except Exception as e:
        logger.error(f"Error in trending_now: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 6) Trending Now by RSS
# -------------------------------------------------------------------------
@google_trends_router.get("/trending-now-by-rss", summary="Google Trends: Trending Now by RSS")
async def trending_now_by_rss(
    geo: Optional[str] = Query("US", description="Geolocation code for trending searches (e.g., 'US')."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves current trending searches by RSS for the specified geo. Includes related news.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_trending_now_by_rss",
            geo=geo
        )

        async def fetch_trending_now_by_rss():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_trending_now_by_rss():
                try:
                    logger.debug(f"Calling TrendSpy API with geo: {geo}")
                    data = trends_obj.trending_now_by_rss(geo=geo)
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for trending_now_by_rss")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing trending_now_by_rss data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_trending_now_by_rss)

            if raw_results is None:
                logger.warning("No trending now by RSS data returned from TrendSpy API")
                return {"data": [], "message": "No trending now by RSS data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process trending now by RSS data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_trending_now_by_rss)

    except Exception as e:
        logger.error(f"Error in trending_now_by_rss: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 7) Trending Now News by IDs
# -------------------------------------------------------------------------
@google_trends_router.get("/trending-now-news-by-ids", summary="Related News by IDs")
async def trending_now_news_by_ids(
    news_tokens: str = Query(..., description="Comma-separated news tokens from a trending topic."),
    max_news: int = Query(3, description="Number of articles to retrieve."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Retrieves related news articles for specified news tokens.
    Adds randomized headers to each API call.
    """
    try:
        logger.debug(f"Received request with tokens: {news_tokens}, max_news: {max_news}")

        token_list = [token.strip() for token in news_tokens.split(",") if token.strip()]
        logger.debug(f"Parsed token list: {token_list}")

        if not token_list:
            logger.warning("No valid tokens found in input")
            raise HTTPException(status_code=400, detail="No valid news tokens provided.")

        # Generate cache key
        cache_key = generate_cache_key(
            "trends_trending_now_news_by_ids",
            news_tokens=news_tokens,
            max_news=max_news
        )

        async def fetch_trending_now_news_by_ids():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_news():
                try:
                    logger.debug(f"Calling TrendSpy API with tokens: {token_list}, max_news: {max_news}")
                    data = trends_obj.trending_now_news_by_ids(token_list, max_news=max_news)
                    logger.debug(f"Raw API response: {data}")

                    # Check if data is None or empty
                    if not data:
                        logger.warning("TrendSpy API returned empty data for trending_now_news_by_ids")
                        return None

                    if not isinstance(data, list):
                        logger.warning(f"TrendSpy API returned non-list data type: {type(data)}")
                        return None

                    if len(data) == 0:
                        logger.warning("TrendSpy API returned empty list for trending_now_news_by_ids")
                        return None

                    logger.debug(f"First element type: {type(data[0])}")
                    logger.debug(f"First element content: {data[0]}")

                    if data[0] is None:
                        logger.warning("First element of API response is None")
                        return None

                    if len(data[0]) < 3:
                        logger.warning(f"First element has insufficient length: {len(data[0])}")
                        return None

                    logger.debug(f"Element at data[0][2] type: {type(data[0][2])}")
                    logger.debug(f"Element at data[0][2] content: {data[0][2]}")

                    news_data = data[0][2]
                    if news_data is None:
                        logger.warning("Required news data element is None")
                        return None

                    # Handle different response types
                    if isinstance(news_data, str):
                        try:
                            parsed_json = json.loads(news_data)
                            data[0][2] = parsed_json
                            logger.debug(f"Successfully parsed JSON data: {parsed_json}")
                        except json.JSONDecodeError as je:
                            logger.error(f"Failed to parse JSON: {je}")
                            return None
                    elif isinstance(news_data, (dict, list)):
                        logger.debug("News data already in JSON format")
                    else:
                        logger.warning(f"Unexpected news data type: {type(news_data)}")
                        return None

                    logger.debug(f"Final validated data structure: {data}")
                    return data

                except (IndexError, TypeError, AttributeError) as e:
                    logger.error(f"Error processing API response: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_news)

            if raw_results is None:
                logger.warning("No valid news data returned from TrendSpy API call")
                return {"data": [], "message": "No news data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process news data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_trending_now_news_by_ids)

    except Exception as e:
        logger.error(f"Error in trending_now_news_by_ids: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 8) Trending Now Showcase Timeline (Independent Historical Data)
# -------------------------------------------------------------------------
@google_trends_router.get("/trending-now-showcase-timeline", summary="Get Trending Timeline")
async def trending_now_showcase_timeline(
    keywords: str = Query(..., description="Comma-separated keywords to analyze"),
    timeframe: HumanFriendlyBatchPeriod = Query(..., description="Timeframe value (past_4h, past_24h, past_48h, past_7d)"),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get trending timeline data for specified keywords.
    Adds randomized headers to each API call.
    """
    try:
        # Parse keywords
        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not keyword_list:
            logger.warning("No valid keywords provided")
            raise HTTPException(status_code=400, detail="No valid keywords provided")

        # Map human-friendly timeframe to BatchPeriod
        timeframe_mapping = {
            HumanFriendlyBatchPeriod.past_4h: BatchPeriod.Past4H,
            HumanFriendlyBatchPeriod.past_24h: BatchPeriod.Past24H,
            HumanFriendlyBatchPeriod.past_48h: BatchPeriod.Past48H,
            HumanFriendlyBatchPeriod.past_7d: BatchPeriod.Past7D
        }

        mapped_timeframe = timeframe_mapping.get(timeframe)
        if not mapped_timeframe:
            logger.warning(f"Invalid timeframe provided: {timeframe}")
            raise HTTPException(status_code=400, detail="Invalid timeframe provided.")

        # Generate cache key
        cache_key = generate_cache_key(
            "trends_trending_now_showcase_timeline",
            keywords=keywords,
            timeframe=timeframe.value
        )

        async def fetch_trending_now_showcase_timeline():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_timeline():
                try:
                    logger.debug(f"Calling TrendSpy API with keywords: {keyword_list}, timeframe: {mapped_timeframe}")
                    data = trends_obj.trending_now_showcase_timeline(
                        keyword_list,
                        timeframe=mapped_timeframe
                    )
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for trending_now_showcase_timeline")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing trending_now_showcase_timeline data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_timeline)

            if raw_results is None:
                logger.warning("No timeline data returned from TrendSpy API call")
                return {"data": [], "message": "No timeline data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process timeline data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_trending_now_showcase_timeline)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in trending_now_showcase_timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 9) Categories
# -------------------------------------------------------------------------
@google_trends_router.get("/categories", summary="Search or List Google Trends Categories")
async def get_categories(
    find: Optional[str] = Query(None, description="String to match category name (e.g., 'tech')."),
    root: Optional[str] = Query(None, description="Root category ID to list subcategories."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Searches or lists categories in the Google Trends taxonomy.
    Adds randomized headers to each API call.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_categories",
            find=find,
            root=root
        )

        async def fetch_categories():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_categories():
                try:
                    logger.debug(f"Calling TrendSpy API with find: {find}, root: {root}")
                    data = trends_obj.categories(find=find)
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for categories")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing categories data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_categories)

            if raw_results is None:
                logger.warning("No categories data returned from TrendSpy API")
                return {"data": [], "message": "No categories data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process categories data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_categories)

    except Exception as e:
        logger.error(f"Error in get_categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# -------------------------------------------------------------------------
# 10) Geo
# -------------------------------------------------------------------------
@google_trends_router.get("/geo", summary="Search or List Google Trends Geolocations")
async def get_geo(
    find: Optional[str] = Query(None, description="String to match location name (e.g., 'york')."),
    rate_limit: None = Depends(rate_limit)
):
    """
    Searches available geolocation codes in Google Trends (countries, states, cities).
    Adds randomized headers to each API call.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "trends_geo",
            find=find
        )

        async def fetch_geo():
            trends_obj = await get_trends_instance()
            logger.debug("TrendSpy instance created successfully")

            def safe_get_geo():
                try:
                    logger.debug(f"Calling TrendSpy API with find: {find}")
                    data = trends_obj.geo(find=find)
                    logger.debug(f"Raw API response: {data}")

                    if data is None:
                        logger.warning("TrendSpy API returned no data for geo")
                        return None

                    return data

                except Exception as e:
                    logger.error(f"Error processing geo data: {e}", exc_info=True)
                    return None

            loop = asyncio.get_event_loop()
            logger.debug("Executing TrendSpy API call asynchronously")
            raw_results = await loop.run_in_executor(None, safe_get_geo)

            if raw_results is None:
                logger.warning("No geo data returned from TrendSpy API")
                return {"data": [], "message": "No geo data was returned."}

            try:
                logger.debug("Converting results to JSON-serializable format")
                data = to_jsonable(raw_results)
                logger.debug(f"Successfully converted data: {data}")
                return {"data": data}
            except Exception as json_err:
                logger.error(f"Error converting results to JSON: {json_err}", exc_info=True)
                return {"data": [], "message": "Failed to process geo data."}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_geo)

    except Exception as e:
        logger.error(f"Error in get_geo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")