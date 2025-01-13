"""
Google Autocomplete API integration for keyword generation.
Generates comprehensive keyword variations using Google Autocomplete suggestions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import get_api_key
from app.core.proxy import get_proxy  # Import get_proxy for proxy handling

import requests
import httpx
import xml.etree.ElementTree as ET
import logging
from typing import Optional
from enum import Enum

class OutputFormat(str, Enum):
    TOOLBAR = "toolbar"
    CHROME = "chrome"
    FIREFOX = "firefox"
    XML = "xml"
    SAFARI = "safari"
    OPERA = "opera"

router = APIRouter()

logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.INFO)


@router.get("/autocomplete-keywords", summary="Generate keyword variations using Google Autocomplete.")
async def generate_keywords(
    input_keyword: str = Query(..., description="Base keyword to generate variations."),
    input_country: str = Query("US", description="Country code for Google Autocomplete."),
    use_proxy: Optional[bool] = Query(
        False,
        description="Enable or disable the use of proxy service for this request. Defaults to disabled."
    ),
    output: OutputFormat = Query(
        ..., 
        description="Output format for Google Autocomplete. Allowed values: 'firefox', 'toolbar', 'chrome', 'xml', 'safari', 'opera'."
    ),
    spell: Optional[int] = Query(
        1,
        description="Controls spell-checking in autocomplete suggestions. `1` to enable, `0` to disable."
    ),
    hl: Optional[str] = Query(
        "en",
        description="The UI language setting (e.g., English, Spanish). Example: &hl=en or &hl=es"
    ),
    ds: Optional[str] = Query(
        "",  # Changed default from "web" to empty string
        description="Specifies a search domain or vertical. Example values: yt (YouTube), news, web."
    ),
    api_key: str = Depends(get_api_key)
):
    """
    Generate a structured list of keyword variations by combining Google Autocomplete
    suggestions across various categories.

    - **input_keyword**: The base keyword for which variations are to be generated.
    - **input_country**: The country code to tailor autocomplete suggestions.
    - **use_proxy**: Optional boolean to enable/disable proxy usage for this request.
    - **output**: The desired output format for the autocomplete response. Allowed values: 'firefox', 'toolbar', 'chrome', 'xml', 'safari', 'opera'.
    - **spell**: Controls spell-checking in autocomplete suggestions. `1` to enable, `0` to disable.
    - **hl**: The UI language setting (e.g., English, Spanish). Example: &hl=en or &hl=es
    - **ds**: Specifies a search domain or vertical. Example values: yt (YouTube), news, web.
    """
    try:
        # Validate output format
        if output not in OutputFormat:
            raise HTTPException(status_code=400, detail="Invalid output format.")
        
        # Determine whether to use proxy based on the 'use_proxy' parameter
        proxy_url = await get_proxy() if use_proxy else None
        if use_proxy and proxy_url:
            logger.debug(f"Proxy enabled for this request: {proxy_url}")
            headers = {}
            mounts = {
                "http://": httpx.AsyncHTTPTransport(proxy=proxy_url),
                "https://": httpx.AsyncHTTPTransport(proxy=proxy_url),
            }
            client = httpx.AsyncClient(mounts=mounts, follow_redirects=True, headers=headers)
        else:
            if use_proxy:
                logger.warning("Proxy was requested but no proxy URL is available. Proceeding without proxy.")
            else:
                logger.debug("Proxy disabled for this request.")
            client = httpx.AsyncClient(follow_redirects=True)

        async with client as http_client:
            keyword_data = await get_suggestion_keywords_google_optimized(
                input_keyword, input_country, output, hl, ds, spell, http_client=http_client
            )

        result = {
            "success": True,
            "message": "Success! Keywords Generated",
            "keyword_data": keyword_data,
        }
        return result
    except Exception as e:
        logger.error(f"Error in generate_keywords: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


async def get_suggestion_keywords_google_optimized(
    query: str, country_code: str, output: OutputFormat, hl: str, ds: str, spell: Optional[int], http_client: httpx.AsyncClient
) -> dict:
    """
    Generates user-centric keyword expansions by combining the base query with
    various category-specific prefixes. Fetches autocomplete suggestions for each
    variation, then organizes them into a category-based dictionary.

    - **query**: The base keyword query.
    - **country_code**: The country code for localization.
    - **output**: The desired output format for the autocomplete response.
    - **hl**: The UI language setting.
    - **ds**: Specifies a search domain or vertical.
    - **spell**: Controls spell-checking in autocomplete suggestions.
    - **http_client**: The configured httpx.AsyncClient instance.
    """
    categories = {
        "Questions": [
            "who", "what", "where", "when", "why", "how", "are",
            "can", "does", "did", "should", "would", "could", "is", "am", "might"
        ],
        "Prepositions": [
            "can", "with", "for", "by", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "under", "over", "within"
        ],
        "Alphabet": list("abcdefghijklmnopqrstuvwxyz"),
        "Comparisons": [
            "vs", "versus", "or", "compared to", "compared with", "against",
            "like", "similar to"
        ],
        "Intent-Based": [
            "buy", "review", "price", "best", "top", "how to", "why to",
            "where to", "find", "get", "download", "install", "learn",
            "use", "compare", "donate", "subscribe", "sign up", "best way to"
        ],
        "Intent-Based - Transactional": [
            "buy", "purchase", "order", "book", "subscribe"
        ],
        "Intent-Based - Informational": [
            "how to", "what is", "tips for", "guide to", "information about"
        ],
        "Intent-Based - Navigational": [
            "official site", "login", "homepage", "contact"
        ],
        "Time-Related": [
            "when", "schedule", "deadline", "today", "now", "latest",
            "future", "upcoming", "recently", "this week", "this month",
            "this year", "current", "historical", "past", "before", "after"
        ],
        "Audience-Specific": [
            "for beginners", "for small businesses", "for students", "for professionals",
            "for teachers", "for developers", "for marketers", "for educators",
            "for entrepreneurs", "for hobbyists", "for seniors", "for children",
            "for parents", "for freelancers", "for startups", "for non-profits"
        ],
        "Problem-Solving": [
            "solution", "issue", "error", "troubleshoot", "fix",
            "how to solve", "how to fix", "common problems",
            "tips for", "overcoming", "resolving", "addressing",
            "dealing with", "combating", "eliminating"
        ],
        "Feature-Specific": [
            "with video", "with images", "analytics", "tools", "with example",
            "with tutorials", "with guides", "with screenshots", "with templates",
            "with case studies", "for mobile", "for desktop", "with API",
            "with integrations", "with extensions", "customizable",
            "premium features", "advanced features"
        ],
        "Opinions/Reviews": [
            "review", "opinion", "rating", "feedback", "testimonial",
            "user reviews", "expert reviews", "customer reviews",
            "unbiased reviews", "honest opinions", "detailed ratings",
            "product testimonials", "service feedback", "peer reviews",
            "trusted reviews"
        ],
        "Cost-Related": [
            "price", "cost", "budget", "cheap", "expensive", "value",
            "affordable", "free", "discount", "promotions", "deals",
            "cheapest", "most affordable", "pricing plans", "cost-effective",
            "low cost", "premium price", "worth the price", "ROI"
        ],
        "Trend-Based": [
            "trends", "new", "upcoming", "latest", "hot", "viral",
            "popular", "current", "2024", "emerging", "now", "breakthrough"
        ],
        "Geographic-Specific": [
            "in New York", "near me", "US based", "local", "regional",
            "global", "Worldwide", "California", "Downtown"
        ],
        "Demographic-Specific": [
            "for seniors", "for millennials", "for Gen Z", "for men",
            "for women", "for families", "for singles", "for couples",
            "for retirees", "for parents", "for teenagers"
        ],
        "Seasonal/Event-Specific": [
            "during Christmas", "for Summer", "Black Friday 2024",
            "Cyber Monday 2024", "Halloween", "Spring", "Fall",
            "Back to School", "New Year", "Easter"
        ],
        "Problem/Need-Based": [
            "how to prevent", "how to manage", "how to improve",
            "how to reduce", "how to increase", "how to enhance",
            "alternatives to", "replacement for", "best practices for",
            "real-life examples of"
        ],
    }

    categorized_suggestions = {key: {} for key in categories.keys()}

    for category, prefixes in categories.items():
        for prefix in prefixes:
            try:
                if category.startswith("Intent-Based"):
                    modified_query = f"{prefix} {query}"
                elif category == "Alphabet":
                    modified_query = f"{query} {prefix}"
                else:
                    modified_query = f"{prefix} {query}"

                suggestions = await get_suggestions_for_query_async(
                    modified_query, country_code, output, hl, ds, spell, http_client=http_client
                )
                categorized_suggestions[category][prefix] = suggestions
            except Exception as e:
                logger.warning(f"Error fetching suggestions for '{modified_query}': {str(e)}")

    return categorized_suggestions


async def get_suggestions_for_query_async(
    query: str, country: str, output: OutputFormat, hl: str, ds: str, spell: Optional[int], http_client: httpx.AsyncClient
) -> list:
    """
    Makes an asynchronous request to Google's autocomplete endpoint and retrieves
    a list of suggestions in lowercase.

    - **query**: The modified query for which suggestions are sought.
    - **country**: The country code to localize the autocomplete suggestions.
    - **output**: The desired output format for the autocomplete response.
    - **hl**: The UI language setting.
    - **ds**: Specifies a search domain or vertical.
    - **spell**: Controls spell-checking in autocomplete suggestions.
    - **http_client**: The configured httpx.AsyncClient instance.
    """
    suggestions = []
    try:
        autocomplete_url = f"https://www.google.com/complete/search?output={output.value}&gl={country}&hl={hl}&ds={ds}&spell={spell}&q={query}"
        logger.debug(f"Making request to: {autocomplete_url}")

        response = await http_client.get(autocomplete_url)

        # Log detailed response info
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")

        if response.status_code == 302:
            redirect_url = response.headers.get('location')
            logger.error(f"Redirect detected to: {redirect_url}")
            logger.error(f"Original URL: {autocomplete_url}")
            logger.error(f"Full response headers: {dict(response.headers)}")
            try:
                logger.error(f"Response body: {response.text}")
            except Exception as e:
                logger.error(f"Could not read response body: {str(e)}")

        if response.status_code != 200:
            logger.error(f"Failed to retrieve suggestions for query '{query}'")
            logger.error(f"Status Code: {response.status_code}")
            logger.error(f"Response Headers: {dict(response.headers)}")
            return suggestions

        try:
            if output in [OutputFormat.XML, OutputFormat.TOOLBAR]:
                root = ET.fromstring(response.content)
                for complete_suggestion in root.findall("CompleteSuggestion"):
                    suggestion_element = complete_suggestion.find("suggestion")
                    if suggestion_element is not None:
                        data = suggestion_element.get("data", "").lower()
                        suggestions.append(data)
            elif output in [OutputFormat.CHROME, OutputFormat.FIREFOX, OutputFormat.SAFARI, OutputFormat.OPERA]:
                data = response.json()
                if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                    if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                        suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                    else:
                        suggestions = [item.lower() for item in data[1]]
            else:
                # Handle other output formats if necessary
                logger.debug(f"No specific handler for output format: {output.value}")
        except ET.ParseError as e:
            logger.error(f"XML Parse Error for query '{query}': {str(e)}")
            logger.error(f"Response Content: {response.text[:200]}...")  # Log first 200 chars
        except ValueError as e:
            logger.error(f"JSON Decode Error for query '{query}': {str(e)}")
            logger.error(f"Response Content: {response.text[:200]}...")  # Log first 200 chars

    except Exception as e:
        logger.error(f"Exception in get_suggestions_for_query_async for query '{query}': {str(e)}", exc_info=True)

    return suggestions


def get_suggestions_for_query(query: str) -> list:
    """
    Synchronously fetch suggestions for a given query.

    - **query**: The query for which suggestions are sought.
    """
    suggestions = []
    try:
        proxy_url = get_proxy()
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        autocomplete_url = f"https://www.google.com/complete/search?output=toolbar&q={query}"
        response = requests.get(autocomplete_url, proxies=proxies)

        if response.status_code != 200:
            logger.error(f"Failed to retrieve suggestions for query '{query}'. Status Code: {response.status_code}")
            return suggestions

        root = ET.fromstring(response.content)
        for complete_suggestion in root.findall("CompleteSuggestion"):
            suggestion_element = complete_suggestion.find("suggestion")
            if suggestion_element is not None:
                data = suggestion_element.get("data", "").lower()
                suggestions.append(data)
    except Exception as e:
        logger.error(f"Exception in get_suggestions_for_query for query '{query}': {str(e)}", exc_info=True)

    return suggestions