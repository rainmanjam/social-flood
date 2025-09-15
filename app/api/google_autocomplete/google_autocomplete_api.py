"""
Google Autocomplete API integration for keyword generation.
Generates comprehensive keyword variations using Google Autocomplete suggestions.

This module provides a FastAPI endpoint for accessing Google's Autocomplete API
with support for all available parameters and output formats.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from app.core.auth import get_api_key
from app.core.proxy import get_proxy  # Import get_proxy for proxy handling
from app.core.config import get_settings
from pydantic import BaseModel, Field, validator
from fastapi.responses import JSONResponse

import requests
import httpx
import xml.etree.ElementTree as ET
import logging
import json
from typing import Optional, List, Dict, Any, Union
import asyncio
from app.core.rate_limiter import rate_limit
from app.core.cache_manager import cache_manager
from enum import Enum
import asyncio
import time
from datetime import datetime
from app.core.http_client import get_http_client_manager
from app.core.input_sanitizer import get_input_sanitizer

# Configure logging
logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.INFO)

# Cache key generation functions
# -----------------------------------------------------------------------------
def generate_cache_key(endpoint: str, **params) -> str:
    """
    Generate a cache key for Google Autocomplete API calls.
    
    Args:
        endpoint: The API endpoint name
        **params: Query parameters
        
    Returns:
        str: Cache key
    """
    # Sort parameters for consistent key generation
    sorted_params = sorted(params.items())
    param_str = "_".join(f"{k}:{v}" for k, v in sorted_params if v is not None)
    return f"autocomplete:{endpoint}:{param_str}"

async def get_cached_or_fetch(key: str, fetch_func, ttl: int = None):
    """
    Get data from cache or fetch and cache it.
    
    Args:
        key: Cache key
        fetch_func: Async function to fetch data if not cached
        ttl: Time to live in seconds
        
    Returns:
        The fetched or cached data
    """
    settings = get_settings()
    if not settings.ENABLE_CACHE:
        return await fetch_func()
    
    # Try to get from cache
    cached_data = await cache_manager.get(key, namespace="autocomplete")
    if cached_data is not None:
        logger.debug(f"Cache hit for key: {key}")
        return cached_data
    
    # Fetch data
    data = await fetch_func()
    
    # Cache the result
    if data:
        ttl = ttl or settings.CACHE_TTL
        await cache_manager.set(key, data, ttl=ttl, namespace="autocomplete")
        logger.debug(f"Cached data for key: {key}, TTL: {ttl}s")
    
    return data

# Enums for parameter validation
class OutputFormat(str, Enum):
    """Output format options for Google Autocomplete API."""
    TOOLBAR = "toolbar"  # XML format used by Google Toolbar, returns CompleteSuggestion elements in XML
    CHROME = "chrome"    # JSON format used by Chrome browser, returns [query, [suggestions], [descriptions], [query_completions], {metadata}]
    FIREFOX = "firefox"  # JSON format used by Firefox browser, similar to Chrome but with simplified structure
    XML = "xml"          # Standard XML format, identical to toolbar format
    SAFARI = "safari"    # JSON format used by Safari browser, similar to Chrome format
    OPERA = "opera"      # JSON format used by Opera browser, similar to Chrome format

class ClientType(str, Enum):
    """Client identifier options for Google Autocomplete API."""
    FIREFOX = "firefox"
    CHROME = "chrome"
    SAFARI = "safari"
    OPERA = "opera"

class DataSource(str, Enum):
    """Data source options for the 'ds' parameter."""
    WEB = ""             # General web search (default)
    YOUTUBE = "yt"       # YouTube video suggestions
    IMAGES = "i"         # Image search suggestions
    NEWS = "n"           # News search suggestions
    SHOPPING = "s"       # Shopping/product suggestions
    VIDEOS = "v"         # Video search suggestions
    BOOKS = "b"          # Book search suggestions
    PATENTS = "p"        # Patent search suggestions
    FINANCE = "fin"      # Financial/stock suggestions
    RECIPES = "recipe"   # Recipe suggestions
    SCHOLAR = "scholar"  # Google Scholar academic suggestions
    PLAY = "play"        # Google Play Store suggestions
    MAPS = "maps"        # Google Maps location suggestions
    FLIGHTS = "flights"  # Google Flights suggestions
    HOTELS = "hotels"    # Google Hotels suggestions

# Pydantic model for request validation
class GoogleAutocompleteParams(BaseModel):
    """
    Pydantic model for Google Autocomplete API parameters.
    
    This model validates and documents all available parameters for the Google
    Autocomplete API based on the comprehensive reference guide.
    """
    # Core Parameters
    q: str = Field(..., description="Search query string (URL encoded)")
    output: OutputFormat = Field(
        OutputFormat.TOOLBAR, 
        description="Response format (toolbar, firefox, chrome, etc.)"
    )
    client: Optional[ClientType] = Field(
        None, 
        description="Client identifier (firefox, chrome, safari, opera)"
    )
    
    # Geographic & Language Parameters
    gl: str = Field(
        "US", 
        description="Geographic location (country) using ISO country codes"
    )
    hl: str = Field(
        "en", 
        description="Host language using ISO language codes"
    )
    cr: Optional[str] = Field(
        None, 
        description="Country restrict (e.g., countryUS, countryUK)"
    )
    
    # Data Source Parameters
    ds: Optional[DataSource] = Field(
        None, 
        description="Data source for suggestions (yt, i, n, s, v, b, p, etc.)"
    )
    
    # Search Enhancement Parameters
    spell: Optional[int] = Field(
        1, 
        description="Enable spell correction (0=disabled, 1=enabled)"
    )
    cp: Optional[int] = Field(
        None, 
        description="Cursor position in query (character position)"
    )
    gs_rn: Optional[int] = Field(
        None, 
        description="Request number for sequential numbering"
    )
    gs_id: Optional[str] = Field(
        None, 
        description="Session ID for tracking"
    )
    
    # Response Parameters
    callback: Optional[str] = Field(
        None, 
        description="JSONP callback function name"
    )
    jsonp: Optional[str] = Field(
        None, 
        description="JSONP wrapper (alternative to callback)"
    )
    
    # Advanced Parameters
    psi: Optional[int] = Field(
        None, 
        description="Personalized search (0=disabled, 1=enabled)"
    )
    pq: Optional[str] = Field(
        None, 
        description="Previous query for query refinement"
    )
    complete: Optional[int] = Field(
        None, 
        description="Completion type affecting completion logic"
    )
    suggid: Optional[str] = Field(
        None, 
        description="Suggestion ID for internal tracking"
    )
    gs_l: Optional[str] = Field(
        None, 
        description="Google search location (internal parameter)"
    )
    
    class Config:
        """Configuration for the Pydantic model."""
        schema_extra = {
            "example": {
                "q": "chrome",
                "output": "chrome",
                "client": "chrome",
                "gl": "US",
                "hl": "en",
                "ds": "yt",
                "spell": 1
            }
        }

# Create router with a specific tag to avoid duplication in documentation
router = APIRouter(tags=["Google Autocomplete API"])


@router.get(
    "/autocomplete", 
    summary="Get raw Google Autocomplete suggestions with all parameters.",
    response_description="Returns raw Google Autocomplete suggestions",
    responses={
        200: {
            "description": "Successful response with autocomplete suggestions",
            "content": {
                "application/json": {
                    "examples": {
                        "XML Format": {
                            "summary": "Response when using XML/toolbar format",
                            "value": {"suggestions": ["python tutorial", "python download", "python for beginners"]}
                        },
                        "JSON Format": {
                            "summary": "Response when using JSON format (chrome/firefox)",
                            "value": {"raw_response": ["python", ["python tutorial", "python download", "python for beginners"]]}
                        }
                    }
                }
            }
        },
        400: {"description": "Bad request - invalid parameters"},
        401: {"description": "Unauthorized - invalid API key"},
        500: {"description": "Internal server error or parsing failure"}
    }
)
async def get_autocomplete(
    q: str = Query(
        ..., 
        description="Search query string (URL encoded)",
        example="chrome",
        title="Query"
    ),
    output: OutputFormat = Query(
        OutputFormat.TOOLBAR, 
        description="Response format (toolbar, firefox, chrome, etc.)",
        example="chrome",
        title="Output Format"
    ),
    client: Optional[ClientType] = Query(
        None, 
        description="Client identifier (firefox, chrome, safari, opera)",
        example="chrome",
        title="Client Identifier"
    ),
    gl: str = Query(
        "US", 
        description="Geographic location (country) using ISO country codes",
        example="US",
        title="Geographic Location"
    ),
    hl: str = Query(
        "en", 
        description="Host language using ISO language codes",
        example="en",
        title="Host Language"
    ),
    cr: Optional[str] = Query(
        None, 
        description="Country restrict parameter. Format is 'country' followed by the ISO country code (e.g., countryUS, countryGB, countryIN)",
        example=None,
        title="Country Restrict"
    ),
    ds: Optional[DataSource] = Query(
        None, 
        description="Data source for suggestions. Controls which Google service to pull suggestions from.",
        example="",
        title="Data Source"
    ),
    spell: Optional[int] = Query(
        None, 
        description="Enable spell correction. Set to 1 to enable, 0 to disable. If not provided, Google's default behavior applies.",
        example=None,
        title="Spell Correction"
    ),
    cp: Optional[int] = Query(
        None, 
        description="Cursor position in query. Specifies the character position where the cursor is located in the query string.",
        example=None,
        title="Cursor Position"
    ),
    gs_rn: Optional[int] = Query(
        None, 
        description="Request number for sequential numbering. Used for tracking multiple requests in a sequence.",
        example=None,
        title="Request Number"
    ),
    gs_id: Optional[str] = Query(
        None, 
        description="Session ID for tracking. Identifies a specific user session for analytics and tracking purposes.",
        example=None,
        title="Session ID"
    ),
    callback: Optional[str] = Query(
        None, 
        description="JSONP callback function name. When specified, the response will be wrapped in this function name.",
        example=None,
        title="JSONP Callback"
    ),
    jsonp: Optional[str] = Query(
        None, 
        description="JSONP wrapper (alternative to callback). Similar to callback, wraps the response in a JavaScript function call.",
        example=None,
        title="JSONP Wrapper"
    ),
    psi: Optional[int] = Query(
        None, 
        description="Personalized search flag. Set to 1 to enable personalized results, 0 to disable.",
        example=None,
        title="Personalized Search"
    ),
    pq: Optional[str] = Query(
        None, 
        description="Previous query for query refinement. Provides context from a previous search query.",
        example=None,
        title="Previous Query"
    ),
    complete: Optional[int] = Query(
        None, 
        description="Completion type affecting suggestion logic. Controls how completions are generated.",
        example=None,
        title="Completion Type"
    ),
    suggid: Optional[str] = Query(
        None, 
        description="Suggestion ID for internal tracking. Used by Google for analytics and tracking.",
        example=None,
        title="Suggestion ID"
    ),
    gs_l: Optional[str] = Query(
        None, 
        description="Google search location codes. Internal parameter used by Google for location-based customization.",
        example=None,
        title="Google Search Location"
    ),
    variations: Optional[bool] = Query(
        False,
        description="If true, returns comprehensive keyword variations instead of raw suggestions",
        example=False,
        title="Generate Variations"
    ),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get Google Autocomplete suggestions with support for all available parameters.
    
    This endpoint provides access to Google's Autocomplete API with comprehensive
    parameter support. It can return either raw suggestions or comprehensive keyword
    variations depending on the 'variations' parameter.
    
    ## Core Parameters
    - **q**: Search query string (required, URL encoded)
    - **output**: Response format (toolbar, firefox, chrome, etc.)
      - **toolbar**: XML format used by Google Toolbar, returns CompleteSuggestion elements in XML
      - **chrome**: JSON format used by Chrome browser, returns [query, [suggestions], [descriptions], [query_completions], {metadata}]
      - **firefox**: JSON format used by Firefox browser, similar to Chrome but with simplified structure
      - **xml**: Standard XML format, identical to toolbar format
      - **safari**: JSON format used by Safari browser, similar to Chrome format
      - **opera**: JSON format used by Opera browser, similar to Chrome format
    - **client**: Client identifier (firefox, chrome, safari, opera)
    
    ## Geographic & Language Parameters
    - **gl**: Geographic location/country (ISO country codes like US, UK)
    - **hl**: Host language (ISO language codes like en, es, fr)
    - **cr**: Country restrict (countryUS, countryUK, etc.)
    
    ## Data Source Parameters
    - **ds**: Data source for suggestions. Controls which Google service to pull suggestions from:
      - **(empty)**: General web search (default)
      - **yt**: YouTube video suggestions
      - **i**: Image search suggestions
      - **n**: News search suggestions
      - **s**: Shopping/product suggestions
      - **v**: Video search suggestions
      - **b**: Book search suggestions
      - **p**: Patent search suggestions
      - **fin**: Financial/stock suggestions
      - **recipe**: Recipe suggestions
      - **scholar**: Google Scholar academic suggestions
      - **play**: Google Play Store suggestions
      - **maps**: Google Maps location suggestions
      - **flights**: Google Flights suggestions
      - **hotels**: Google Hotels suggestions
    
    ## Search Enhancement Parameters
    - **spell**: Enable spell correction (0=disabled, 1=enabled)
    - **cp**: Cursor position in query (character position)
    - **gs_rn**: Request number for sequential numbering
    - **gs_id**: Session ID for tracking
    
    ## Response Parameters
    - **callback**: JSONP callback function name
    - **jsonp**: JSONP wrapper (alternative to callback)
    
    ## Advanced Parameters
    - **psi**: Personalized search (0=disabled, 1=enabled)
    - **pq**: Previous query for query refinement
    - **complete**: Completion type affecting completion logic
    - **suggid**: Suggestion ID for internal tracking
    - **gs_l**: Google search location codes (internal parameter)
    
    ## Variations Mode
    - **variations**: When set to true, returns comprehensive keyword variations instead of raw suggestions
    
    ## Response Format
    
    ### Standard Mode (variations=false)
    Returns a JSON object with the raw suggestions and metadata from Google Autocomplete:
    ```json
    {
      "response_type": "json",
      "original_query": "python",
      "suggestions": ["python tutorial", "python download", "python for beginners"],
      "descriptions": [],
      "query_completions": [],
      "metadata": {
        "google:clientdata": {"bpc": true, "tlw": false},
        "google:suggesttype": ["QUERY", "QUERY", "QUERY"],
        "google:verbatimrelevance": 1300
      },
      "raw_response": ["python", ["python tutorial", "python download", "python for beginners"], [], [], {"google:clientdata": {"bpc": true, "tlw": false}, "google:suggesttype": ["QUERY", "QUERY", "QUERY"], "google:verbatimrelevance": 1300}]
    }
    ```
    
    ### JSONP Response Format
    When using callback or jsonp parameters, the response includes the callback name:
    ```json
    {
      "callback": "myCallback",
      "response_type": "jsonp",
      "original_query": "python",
      "suggestions": ["python tutorial", "python download", "python for beginners"],
      "descriptions": [],
      "query_completions": [],
      "metadata": {
        "google:clientdata": {"bpc": true, "tlw": false},
        "google:suggesttype": ["QUERY", "QUERY", "QUERY"],
        "google:verbatimrelevance": 1300
      },
      "raw_response": ["python", ["python tutorial", "python download", "python for beginners"], [], [], {"google:clientdata": {"bpc": true, "tlw": false}, "google:suggesttype": ["QUERY", "QUERY", "QUERY"], "google:verbatimrelevance": 1300}]
    }
    ```
    
    ### Variations Mode (variations=true)
    Returns a comprehensive set of keyword variations organized by category, with metadata for each query:
    ```json
    {
      "success": true,
      "message": "Success! Keywords Generated",
      "keyword_data": {
        "suggestions": {
          "Questions": {
            "what": ["what is python", "what python version", ...],
            "how": ["how to python", "how python works", ...],
            ...
          },
          "Intent-Based": {
            "buy": ["buy python book", "buy python course", ...],
            ...
          },
          ...
        },
        "metadata": {
          "Questions:what": {
            "query": "what python",
            "metadata": {
              "google:clientdata": {"bpc": true, "tlw": false},
              "google:suggesttype": ["QUERY", "QUERY", "QUERY"],
              "google:verbatimrelevance": 1300
            },
            "response_type": "json"
          },
          "Questions:how": {
            "query": "how python",
            "metadata": {
              "google:clientdata": {"bpc": true, "tlw": false},
              "google:suggesttype": ["QUERY", "QUERY", "QUERY"],
              "google:verbatimrelevance": 1300
            },
            "response_type": "json"
          },
          ...
        }
      }
    }
    ```
    
    ## Metadata Fields
    
    The metadata object may contain various fields from Google, including:
    
    - **google:clientdata**: Client-specific flags and settings
      - **bpc**: Bypass cache flag
      - **tlw**: Top level widget flag
    - **google:suggesttype**: Types of suggestions returned (e.g., "QUERY", "NAVIGATION")
    - **google:suggestrelevance**: Relevance scores for each suggestion
    - **google:suggestsubtypes**: Subtypes for each suggestion
    - **google:verbatimrelevance**: Relevance score for the exact query
    
    This endpoint combines the functionality of both `/autocomplete` and `/autocomplete/variations`
    into a single endpoint, making it easier to switch between raw suggestions and comprehensive
    keyword variations.
    """
    try:
        # Get proxy configuration
        proxy_url = await get_proxy()

        # Get HTTP client manager and input sanitizer
        http_manager = get_http_client_manager()
        sanitizer = get_input_sanitizer()

        # Start timing for response metadata
        start_time = time.time()

        # Sanitize and validate all input parameters
        if sanitizer.settings.INPUT_SANITIZATION_ENABLED:
            validation_result = sanitizer.validate_all_params(
                q=q, gl=gl, hl=hl, cr=cr, ds=ds, spell=spell, cp=cp,
                gs_rn=gs_rn, gs_id=gs_id, callback=callback, jsonp=jsonp,
                psi=psi, pq=pq, complete=complete, suggid=suggid, gs_l=gs_l
            )

            if not validation_result["valid"]:
                logger.warning("Input validation failed: %s", validation_result["errors"])
                # Use sanitized values where possible
                if "query" in validation_result["results"]:
                    q = validation_result["results"]["query"]["sanitized"]
                if "country_code" in validation_result["results"]:
                    gl = validation_result["results"]["country_code"]["sanitized"]
                if "language_code" in validation_result["results"]:
                    hl = validation_result["results"]["language_code"]["sanitized"]

        # Set up HTTP client with proxy if available
        if proxy_url:
            logger.debug("Using proxy from environment settings: %s", proxy_url)
        else:
            logger.debug("No proxy configured in environment. Proceeding without proxy.")

        # If variations is True, use the variations endpoint functionality
        if variations:
            logger.info(f"Generating keyword variations for query: {q}")

            # Get settings for parallel processing configuration
            settings = get_settings()
            max_parallel = settings.AUTOCOMPLETE_MAX_PARALLEL_REQUESTS

            # Convert ds to string value if provided
            ds_value = ds if ds else ""

            # Use HTTP client manager for the request
            async with http_manager.get_client(proxy_url) as http_client:
                keyword_data = await get_suggestion_keywords_google_optimized_parallel(
                    query=q,
                    country_code=gl,
                    output=output,
                    hl=hl,
                    ds=ds_value,
                    spell=spell,
                    http_client=http_client,
                    max_parallel=max_parallel,
                    client=client,
                    cr=cr,
                    cp=cp,
                    gs_rn=gs_rn,
                    gs_id=gs_id,
                    callback=callback,
                    jsonp=jsonp,
                    psi=psi,
                    pq=pq,
                    complete=complete,
                    suggid=suggid,
                    gs_l=gs_l
                )

                # Calculate response time and add metadata
                end_time = time.time()
                response_time = end_time - start_time

                result = {
                    "success": True,
                    "message": "Success! Keywords Generated",
                    "keyword_data": keyword_data,
                    "response_metadata": {
                        "response_time_seconds": response_time,
                        "timestamp": datetime.now().isoformat(),
                        "request_count": http_manager.get_request_count(),
                        "connection_pool_stats": http_manager.get_connection_stats()
                    }
                }
                return result

        # Standard autocomplete functionality
        # Generate cache key
        cache_key = generate_cache_key(
            "autocomplete",
            q=q,
            output=output.value,
            client=client.value if client else None,
            gl=gl,
            hl=hl,
            cr=cr,
            ds=ds,
            spell=spell,
            cp=cp,
            gs_rn=gs_rn,
            gs_id=gs_id,
            callback=callback,
            jsonp=jsonp,
            psi=psi,
            pq=pq,
            complete=complete,
            suggid=suggid,
            gs_l=gs_l
        )

        async def fetch_autocomplete_suggestions():
            # Build URL with all provided parameters
            params = {
                "q": q,
                "output": output.value,
                "gl": gl,
                "hl": hl,
                "spell": spell
            }

            # Add optional parameters if provided
            if client:
                params["client"] = client.value
            if cr:
                params["cr"] = cr
            if ds:
                params["ds"] = ds
            if cp is not None:
                params["cp"] = cp
            if gs_rn is not None:
                params["gs_rn"] = gs_rn
            if gs_id:
                params["gs_id"] = gs_id
            if callback:
                params["callback"] = callback
            if jsonp:
                params["jsonp"] = jsonp
            if psi is not None:
                params["psi"] = psi
            if pq:
                params["pq"] = pq
            if complete is not None:
                params["complete"] = complete
            if suggid:
                params["suggid"] = suggid
            if gs_l:
                params["gs_l"] = gs_l

            # Make request using HTTP client manager
            async with http_manager.get_client(proxy_url) as http_client:
                response = await http_client.get(
                    "https://www.google.com/complete/search",
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to retrieve suggestions. Status Code: {response.status_code}")
                    raise HTTPException(status_code=response.status_code, detail="Failed to retrieve suggestions")

                # Calculate response time
                end_time = time.time()
                response_time = end_time - start_time

                # Determine the actual response format based on parameters and content
                # When client parameter is specified, Google usually returns JSON regardless of output parameter
                should_try_json_first = client is not None or output in [OutputFormat.CHROME, OutputFormat.FIREFOX, OutputFormat.SAFARI, OutputFormat.OPERA]

                # Log the first 100 characters of the response for debugging
                response_preview = response.text[:100] if response.text else "Empty response"
                logger.debug(f"Response preview: {response_preview}...")

                # Check if response looks like JSON (starts with [ or {) or JSONP (contains callback function)
                response_text = response.text.strip() if response.text else ""
                looks_like_json = response_text.startswith(('[', '{'))
                looks_like_jsonp = (callback or jsonp) and "(" in response_text and response_text.endswith(")")

                # Smart response parsing - try the most likely format first, then fall back
                if should_try_json_first or looks_like_json or looks_like_jsonp:
                    # Try JSON parsing first
                    try:
                        # Handle JSONP response (callback wrapped JSON)
                        if looks_like_jsonp:
                            logger.debug("Detected JSONP response, extracting JSON data")
                            # Extract JSON data from JSONP wrapper
                            # Format is typically: callback_name({"data": "value"});
                            callback_name = response_text[:response_text.find('(')]
                            start_idx = response_text.find('(')
                            end_idx = response_text.rfind(')')

                            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                                json_str = response_text[start_idx + 1:end_idx]
                                data = json.loads(json_str)

                                # Parse the Google Autocomplete response structure
                                # Format is typically: [query, [suggestions], [descriptions], [query_completions], {metadata}]
                                parsed_response = {
                                    "callback": callback_name,
                                    "response_type": "jsonp",
                                    "original_query": data[0] if len(data) > 0 else "",
                                    "suggestions": data[1] if len(data) > 1 else [],
                                    "descriptions": data[2] if len(data) > 2 else [],
                                    "query_completions": data[3] if len(data) > 3 else [],
                                    "metadata": data[4] if len(data) > 4 else {},
                                    "raw_response": data,
                                    "response_metadata": {
                                        "response_time_seconds": response_time,
                                        "timestamp": datetime.now().isoformat(),
                                        "request_count": http_manager.get_request_count(),
                                        "connection_pool_stats": http_manager.get_connection_stats()
                                    }
                                }

                                # Log detailed information about the response
                                logger.debug(f"Parsed JSONP response: query='{parsed_response['original_query']}', " +
                                            f"suggestions_count={len(parsed_response['suggestions'])}, " +
                                            f"metadata={json.dumps(parsed_response['metadata'])}")

                                return parsed_response
                            else:
                                logger.warning("Failed to extract JSON from JSONP response")
                                return {"raw_response": response_text, "response_type": "raw_jsonp"}
                        else:
                            # Regular JSON response
                            data = response.json()

                            # Check if this is a Google Autocomplete array format
                            if isinstance(data, list) and len(data) >= 2:
                                parsed_response = {
                                    "response_type": "json",
                                    "original_query": data[0] if len(data) > 0 else "",
                                    "suggestions": data[1] if len(data) > 1 else [],
                                    "descriptions": data[2] if len(data) > 2 else [],
                                    "query_completions": data[3] if len(data) > 3 else [],
                                    "metadata": data[4] if len(data) > 4 else {},
                                    "raw_response": data,
                                    "response_metadata": {
                                        "response_time_seconds": response_time,
                                        "timestamp": datetime.now().isoformat(),
                                        "request_count": http_manager.get_request_count(),
                                        "connection_pool_stats": http_manager.get_connection_stats()
                                    }
                                }
                                return parsed_response
                            else:
                                # Unknown JSON format, return as is
                                return {"raw_response": data, "response_type": "json"}
                    except ValueError as e:
                        logger.warning(f"JSON parsing failed, falling back to XML: {str(e)}")
                        # If client is specified but JSON parsing failed, log a warning about parameter conflict
                        if client is not None:
                            logger.warning(f"Parameter conflict: client={client.value} specified but response is not valid JSON")

                        # If callback or jsonp is specified, the response might be a malformed JSONP
                        if callback or jsonp:
                            logger.warning(f"JSONP parameters specified but couldn't parse response: callback={callback}, jsonp={jsonp}")
                            # Return the raw response for debugging
                            return {"raw_response": response_text, "response_type": "unparseable_jsonp"}

                        # Only fall back to XML if output is XML/toolbar
                        if output in [OutputFormat.XML, OutputFormat.TOOLBAR]:
                            try:
                                root = ET.fromstring(response.content)
                                suggestions = []
                                for complete_suggestion in root.findall("CompleteSuggestion"):
                                    suggestion_element = complete_suggestion.find("suggestion")
                                    if suggestion_element is not None:
                                        data = suggestion_element.get("data", "")
                                        suggestions.append(data)
                                return {"suggestions": suggestions}
                            except ET.ParseError as e:
                                logger.error(f"XML Parse Error: {str(e)}")
                                logger.error(f"Response content: {response.text[:500]}...")
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Failed to parse response as XML or JSON. Parameter conflict may exist between output={output.value} and client={client.value if client else 'None'}"
                                )
                        else:
                            # Return raw text if both JSON and XML parsing failed
                            logger.warning("Both JSON and XML parsing failed, returning raw response")
                            return {"raw_response": response.text}
                else:
                    # Try XML parsing first for toolbar/XML output formats
                    try:
                        root = ET.fromstring(response.content)
                        suggestions = []
                        for complete_suggestion in root.findall("CompleteSuggestion"):
                            suggestion_element = complete_suggestion.find("suggestion")
                            if suggestion_element is not None:
                                data = suggestion_element.get("data", "")
                                suggestions.append(data)
                        return {"suggestions": suggestions}
                    except ET.ParseError as e:
                        logger.warning(f"XML parsing failed, trying JSON: {str(e)}")

                        # Fall back to JSON parsing
                        try:
                            data = response.json()
                            return {"raw_response": data}
                        except ValueError as e2:
                            logger.error(f"Both XML and JSON parsing failed: {str(e2)}")
                            logger.error(f"Response content: {response.text[:500]}...")
                            raise HTTPException(
                                status_code=500,
                                detail="Failed to parse response as either XML or JSON"
                            )

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_autocomplete_suggestions)

    except Exception as e:
        logger.error(f"Error in get_autocomplete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# This endpoint has been removed and its functionality combined with the main /autocomplete endpoint
# using the variations parameter. See the main endpoint for documentation.


async def get_suggestion_keywords_google_optimized(
    query: str, 
    country_code: str, 
    output: OutputFormat, 
    hl: str, 
    ds: str, 
    spell: Optional[int], 
    http_client: httpx.AsyncClient,
    client: Optional[ClientType] = None,
    cr: Optional[str] = None,
    cp: Optional[int] = None,
    gs_rn: Optional[int] = None,
    gs_id: Optional[str] = None,
    callback: Optional[str] = None,
    jsonp: Optional[str] = None,
    psi: Optional[int] = None,
    pq: Optional[str] = None,
    complete: Optional[int] = None,
    suggid: Optional[str] = None,
    gs_l: Optional[str] = None
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
    metadata_collection = {}  # Store metadata for each query

    for category, prefixes in categories.items():
        for prefix in prefixes:
            try:
                if category.startswith("Intent-Based"):
                    modified_query = f"{prefix} {query}"
                elif category == "Alphabet":
                    modified_query = f"{query} {prefix}"
                else:
                    modified_query = f"{prefix} {query}"

                # Get full response including metadata
                response_data = await get_suggestions_for_query_async_with_metadata(
                    query=modified_query, 
                    country=country_code, 
                    output=output, 
                    hl=hl, 
                    ds=ds, 
                    spell=spell, 
                    http_client=http_client,
                    client=client,
                    cr=cr,
                    cp=cp,
                    gs_rn=gs_rn,
                    gs_id=gs_id,
                    callback=callback,
                    jsonp=jsonp,
                    psi=psi,
                    pq=pq,
                    complete=complete,
                    suggid=suggid,
                    gs_l=gs_l
                )
                
                # Store suggestions in categorized format
                categorized_suggestions[category][prefix] = response_data["suggestions"]
                
                # Store metadata separately
                if response_data.get("metadata"):
                    query_key = f"{category}:{prefix}"
                    metadata_collection[query_key] = {
                        "query": modified_query,
                        "metadata": response_data.get("metadata", {}),
                        "response_type": response_data.get("response_type", "unknown")
                    }
                    
                    # Log interesting metadata if available
                    if "google:verbatimrelevance" in str(response_data.get("metadata", {})):
                        logger.info(f"Found verbatimrelevance for '{modified_query}': {response_data['metadata']}")
                
            except Exception as e:
                logger.warning(f"Error fetching suggestions for '{modified_query}': {str(e)}")

    # Return both categorized suggestions and metadata
    return {
        "suggestions": categorized_suggestions,
        "metadata": metadata_collection
    }


async def get_suggestion_keywords_google_optimized_parallel(
    query: str, 
    country_code: str, 
    output: OutputFormat, 
    hl: str, 
    ds: str, 
    spell: Optional[int], 
    http_client: httpx.AsyncClient,
    max_parallel: int = 10,
    client: Optional[ClientType] = None,
    cr: Optional[str] = None,
    cp: Optional[int] = None,
    gs_rn: Optional[int] = None,
    gs_id: Optional[str] = None,
    callback: Optional[str] = None,
    jsonp: Optional[str] = None,
    psi: Optional[int] = None,
    pq: Optional[str] = None,
    complete: Optional[int] = None,
    suggid: Optional[str] = None,
    gs_l: Optional[str] = None
) -> dict:
    """
    Generates user-centric keyword expansions using parallel processing.
    Fetches autocomplete suggestions for each variation concurrently using asyncio.gather.
    
    - **query**: The base keyword query.
    - **country_code**: The country code for localization.
    - **output**: The desired output format for the autocomplete response.
    - **hl**: The UI language setting.
    - **ds**: Specifies a search domain or vertical.
    - **spell**: Controls spell-checking in autocomplete suggestions.
    - **http_client**: The configured httpx.AsyncClient instance.
    - **max_parallel**: Maximum number of parallel requests to make.
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
    metadata_collection = {}  # Store metadata for each query
    
    # Create a list of all tasks to be executed
    tasks = []
    task_info = []  # Store info about each task for later processing
    
    for category, prefixes in categories.items():
        for prefix in prefixes:
            if category.startswith("Intent-Based"):
                modified_query = f"{prefix} {query}"
            elif category == "Alphabet":
                modified_query = f"{query} {prefix}"
            else:
                modified_query = f"{prefix} {query}"
            
            # Create task for this query
            task = get_suggestions_for_query_async_with_metadata(
                query=modified_query, 
                country=country_code, 
                output=output, 
                hl=hl, 
                ds=ds, 
                spell=spell, 
                http_client=http_client,
                client=client,
                cr=cr,
                cp=cp,
                gs_rn=gs_rn,
                gs_id=gs_id,
                callback=callback,
                jsonp=jsonp,
                psi=psi,
                pq=pq,
                complete=complete,
                suggid=suggid,
                gs_l=gs_l
            )
            
            tasks.append(task)
            task_info.append({
                "category": category,
                "prefix": prefix,
                "query": modified_query
            })
    
    logger.info(f"Starting parallel processing of {len(tasks)} variation queries with max_parallel={max_parallel}")
    
    # Process tasks in batches to respect the parallel limit
    all_results = []
    for i in range(0, len(tasks), max_parallel):
        batch_tasks = tasks[i:i + max_parallel]
        batch_info = task_info[i:i + max_parallel]
        
        logger.debug(f"Processing batch {i//max_parallel + 1} with {len(batch_tasks)} tasks")
        
        try:
            # Execute batch in parallel
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(batch_results):
                info = batch_info[j]
                if isinstance(result, Exception):
                    logger.warning(f"Error fetching suggestions for '{info['query']}': {str(result)}")
                    # Store empty result for failed requests
                    categorized_suggestions[info["category"]][info["prefix"]] = []
                else:
                    # Store successful results
                    categorized_suggestions[info["category"]][info["prefix"]] = result["suggestions"]
                    
                    # Store metadata separately
                    if result.get("metadata"):
                        query_key = f"{info['category']}:{info['prefix']}"
                        metadata_collection[query_key] = {
                            "query": info["query"],
                            "metadata": result.get("metadata", {}),
                            "response_type": result.get("response_type", "unknown")
                        }
                        
                        # Log interesting metadata if available
                        if "google:verbatimrelevance" in str(result.get("metadata", {})):
                            logger.info(f"Found verbatimrelevance for '{info['query']}': {result['metadata']}")
        
        except Exception as e:
            logger.error(f"Error processing batch {i//max_parallel + 1}: {str(e)}")
            # Continue with next batch even if this one fails
    
    logger.info(f"Completed parallel processing of {len(tasks)} variation queries")
    
    # Return both categorized suggestions and metadata
    return {
        "suggestions": categorized_suggestions,
        "metadata": metadata_collection
    }


async def get_suggestions_for_query_async_with_metadata(
    query: str, 
    country: str, 
    output: OutputFormat, 
    hl: str, 
    ds: str, 
    spell: Optional[int], 
    http_client: httpx.AsyncClient,
    client: Optional[ClientType] = None,
    cr: Optional[str] = None,
    cp: Optional[int] = None,
    gs_rn: Optional[int] = None,
    gs_id: Optional[str] = None,
    callback: Optional[str] = None,
    jsonp: Optional[str] = None,
    psi: Optional[int] = None,
    pq: Optional[str] = None,
    complete: Optional[int] = None,
    suggid: Optional[str] = None,
    gs_l: Optional[str] = None
) -> dict:
    """
    Makes an asynchronous request to Google's autocomplete endpoint and retrieves
    a structured response including suggestions and metadata.
    
    Returns a dictionary with suggestions list and metadata.
    """
    result = {
        "suggestions": [],
        "original_query": query,
        "metadata": {},
        "response_type": "unknown"
    }
    
    try:
        # Build parameters dictionary
        params = {
            "q": query,
            "output": output.value,
            "gl": country,
            "hl": hl,
            "spell": spell
        }
        
        # Add ds parameter if provided and not empty
        if ds:
            params["ds"] = ds
            
        # Add optional parameters if provided
        if client:
            params["client"] = client.value
        if cr:
            params["cr"] = cr
        if cp is not None:
            params["cp"] = cp
        if gs_rn is not None:
            params["gs_rn"] = gs_rn
        if gs_id:
            params["gs_id"] = gs_id
        if callback:
            params["callback"] = callback
        if jsonp:
            params["jsonp"] = jsonp
        if psi is not None:
            params["psi"] = psi
        if pq:
            params["pq"] = pq
        if complete is not None:
            params["complete"] = complete
        if suggid:
            params["suggid"] = suggid
        if gs_l:
            params["gs_l"] = gs_l
            
        logger.debug(f"Making request with parameters: {params}")
        
        # Make request with parameters
        response = await http_client.get("https://www.google.com/complete/search", params=params)

        if response.status_code != 200:
            logger.error(f"Failed to retrieve suggestions for query '{query}'")
            logger.error(f"Status Code: {response.status_code}")
            return result

        # Determine the actual response format based on parameters and content
        should_try_json_first = client is not None or output in [OutputFormat.CHROME, OutputFormat.FIREFOX, OutputFormat.SAFARI, OutputFormat.OPERA]
        
        # Check if response looks like JSON or JSONP
        response_text = response.text.strip() if response.text else ""
        looks_like_json = response_text.startswith(('[', '{'))
        looks_like_jsonp = (callback or jsonp) and "(" in response_text and response_text.endswith(")")
        
        # Smart response parsing - try the most likely format first
        if should_try_json_first or looks_like_json or looks_like_jsonp:
            try:
                # Handle JSONP response
                if looks_like_jsonp:
                    logger.debug(f"Detected JSONP response for query '{query}'")
                    callback_name = response_text[:response_text.find('(')]
                    start_idx = response_text.find('(')
                    end_idx = response_text.rfind(')')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        json_str = response_text[start_idx + 1:end_idx]
                        data = json.loads(json_str)
                        
                        # Update result with parsed data
                        result["response_type"] = "jsonp"
                        result["callback"] = callback_name
                        result["original_query"] = data[0] if len(data) > 0 else query
                        
                        # Extract suggestions
                        if len(data) > 1 and isinstance(data[1], list):
                            if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                                result["suggestions"] = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                            else:
                                result["suggestions"] = [item.lower() for item in data[1]]
                        
                        # Extract metadata
                        if len(data) > 4 and isinstance(data[4], dict):
                            result["metadata"] = data[4]
                            
                        # Store raw response
                        result["raw_response"] = data
                else:
                    # Regular JSON response
                    data = response.json()
                    result["response_type"] = "json"
                    
                    if isinstance(data, list):
                        result["original_query"] = data[0] if len(data) > 0 else query
                        
                        # Extract suggestions
                        if len(data) > 1 and isinstance(data[1], list):
                            if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                                result["suggestions"] = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                            else:
                                result["suggestions"] = [item.lower() for item in data[1]]
                        
                        # Extract metadata
                        if len(data) > 4 and isinstance(data[4], dict):
                            result["metadata"] = data[4]
                            
                        # Store raw response
                        result["raw_response"] = data
            except ValueError as e:
                logger.warning(f"JSON parsing failed for query '{query}': {str(e)}")
                
                # Try XML parsing if JSON fails
                if output in [OutputFormat.XML, OutputFormat.TOOLBAR]:
                    try:
                        root = ET.fromstring(response.content)
                        result["response_type"] = "xml"
                        suggestions = []
                        
                        for complete_suggestion in root.findall("CompleteSuggestion"):
                            suggestion_element = complete_suggestion.find("suggestion")
                            if suggestion_element is not None:
                                data = suggestion_element.get("data", "").lower()
                                suggestions.append(data)
                                
                        result["suggestions"] = suggestions
                    except ET.ParseError as e:
                        logger.error(f"XML Parse Error for query '{query}': {str(e)}")
        else:
            # Try XML parsing first for toolbar/XML output formats
            try:
                root = ET.fromstring(response.content)
                result["response_type"] = "xml"
                suggestions = []
                
                for complete_suggestion in root.findall("CompleteSuggestion"):
                    suggestion_element = complete_suggestion.find("suggestion")
                    if suggestion_element is not None:
                        data = suggestion_element.get("data", "").lower()
                        suggestions.append(data)
                        
                result["suggestions"] = suggestions
            except ET.ParseError as e:
                logger.warning(f"XML parsing failed for query '{query}': {str(e)}")
                
                # Fall back to JSON parsing
                try:
                    data = response.json()
                    result["response_type"] = "json"
                    
                    if isinstance(data, list):
                        result["original_query"] = data[0] if len(data) > 0 else query
                        
                        # Extract suggestions
                        if len(data) > 1 and isinstance(data[1], list):
                            if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                                result["suggestions"] = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                            else:
                                result["suggestions"] = [item.lower() for item in data[1]]
                        
                        # Extract metadata
                        if len(data) > 4 and isinstance(data[4], dict):
                            result["metadata"] = data[4]
                            
                        # Store raw response
                        result["raw_response"] = data
                except ValueError:
                    logger.error(f"Both XML and JSON parsing failed for query '{query}'")

    except Exception as e:
        logger.error(f"Exception in get_suggestions_for_query_async_with_metadata for query '{query}': {str(e)}", exc_info=True)

    return result


async def get_suggestions_for_query_async(
    query: str, 
    country: str, 
    output: OutputFormat, 
    hl: str, 
    ds: str, 
    spell: Optional[int], 
    http_client: httpx.AsyncClient,
    client: Optional[ClientType] = None,
    cr: Optional[str] = None,
    cp: Optional[int] = None,
    gs_rn: Optional[int] = None,
    gs_id: Optional[str] = None,
    callback: Optional[str] = None,
    jsonp: Optional[str] = None,
    psi: Optional[int] = None,
    pq: Optional[str] = None,
    complete: Optional[int] = None,
    suggid: Optional[str] = None,
    gs_l: Optional[str] = None
) -> list:
    """
    Makes an asynchronous request to Google's autocomplete endpoint and retrieves
    a list of suggestions in lowercase.

    ## Core Parameters
    - **query**: The modified query for which suggestions are sought.
    - **country**: The country code to localize the autocomplete suggestions.
    - **output**: The desired output format for the autocomplete response.
    - **hl**: The UI language setting.
    - **ds**: Specifies a search domain or vertical.
    - **spell**: Controls spell-checking in autocomplete suggestions.
    - **http_client**: The configured httpx.AsyncClient instance.
    
    ## Additional Parameters
    - **client**: Client identifier (firefox, chrome, safari, opera)
    - **cr**: Country restrict (e.g., countryUS, countryUK)
    - **cp**: Cursor position in query
    - **gs_rn**: Request number for sequential numbering
    - **gs_id**: Session ID for tracking
    - **callback**: JSONP callback function name
    - **jsonp**: JSONP wrapper (alternative to callback)
    - **psi**: Personalized search (0=disabled, 1=enabled)
    - **pq**: Previous query for query refinement
    - **complete**: Completion type affecting completion logic
    - **suggid**: Suggestion ID for internal tracking
    - **gs_l**: Google search location codes (internal parameter)
    """
    suggestions = []
    try:
        # Build parameters dictionary
        params = {
            "q": query,
            "output": output.value,
            "gl": country,
            "hl": hl,
            "spell": spell
        }
        
        # Add ds parameter if provided and not empty
        if ds:
            params["ds"] = ds
            
        # Add optional parameters if provided
        if client:
            params["client"] = client.value
        if cr:
            params["cr"] = cr
        if cp is not None:
            params["cp"] = cp
        if gs_rn is not None:
            params["gs_rn"] = gs_rn
        if gs_id:
            params["gs_id"] = gs_id
        if callback:
            params["callback"] = callback
        if jsonp:
            params["jsonp"] = jsonp
        if psi is not None:
            params["psi"] = psi
        if pq:
            params["pq"] = pq
        if complete is not None:
            params["complete"] = complete
        if suggid:
            params["suggid"] = suggid
        if gs_l:
            params["gs_l"] = gs_l
            
        logger.debug(f"Making request with parameters: {params}")
        
        # Make request with parameters
        response = await http_client.get("https://www.google.com/complete/search", params=params)

        # Log detailed response info
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")

        if response.status_code == 302:
            redirect_url = response.headers.get('location')
            logger.error(f"Redirect detected to: {redirect_url}")
            logger.error(f"Original parameters: {params}")
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

        # Determine the actual response format based on parameters and content
        # When client parameter is specified, Google usually returns JSON regardless of output parameter
        should_try_json_first = client is not None or output in [OutputFormat.CHROME, OutputFormat.FIREFOX, OutputFormat.SAFARI, OutputFormat.OPERA]
        
        # Check if response looks like JSON (starts with [ or {) or JSONP (contains callback function)
        response_text = response.text.strip() if response.text else ""
        looks_like_json = response_text.startswith(('[', '{'))
        looks_like_jsonp = (callback or jsonp) and "(" in response_text and response_text.endswith(")")
        
        # Smart response parsing - try the most likely format first, then fall back
        if should_try_json_first or looks_like_json or looks_like_jsonp:
            # Try JSON parsing first
            try:
                # Handle JSONP response (callback wrapped JSON)
                if looks_like_jsonp:
                    logger.debug(f"Detected JSONP response for query '{query}', extracting JSON data")
                    # Extract JSON data from JSONP wrapper
                    # Format is typically: callback_name({"data": "value"});
                    start_idx = response_text.find('(')
                    end_idx = response_text.rfind(')')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        json_str = response_text[start_idx + 1:end_idx]
                        data = json.loads(json_str)
                        # Process the extracted JSON data and capture metadata
                        # Format is typically: [query, [suggestions], [descriptions], [query_completions], {metadata}]
                        if isinstance(data, list):
                            # Log metadata if available
                            if len(data) > 4 and isinstance(data[4], dict):
                                metadata = data[4]
                                logger.debug(f"JSONP response metadata for query '{query}': {json.dumps(metadata)}")
                            
                            # Extract suggestions from element 1
                            if len(data) > 1 and isinstance(data[1], list):
                                if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                                    suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                                else:
                                    suggestions = [item.lower() for item in data[1]]
                                
                                # If no suggestions were found but we have metadata, log it for debugging
                                if not suggestions and len(data) > 4 and isinstance(data[4], dict):
                                    logger.info(f"No suggestions found for query '{query}', but metadata is available: {json.dumps(data[4])}")
                    else:
                        logger.warning(f"Failed to extract JSON from JSONP response for query '{query}'")
                else:
                    # Regular JSON response
                    data = response.json()
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                            suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                        else:
                            suggestions = [item.lower() for item in data[1]]
            except ValueError as e:
                logger.warning(f"JSON parsing failed for query '{query}', falling back to XML: {str(e)}")
                # If client is specified but JSON parsing failed, log a warning about parameter conflict
                if client is not None:
                    logger.warning(f"Parameter conflict: client={client.value} specified but response is not valid JSON")
                
                # If callback or jsonp is specified, the response might be a malformed JSONP
                if callback or jsonp:
                    logger.warning(f"JSONP parameters specified but couldn't parse response for query '{query}': callback={callback}, jsonp={jsonp}")
                
                # Only fall back to XML if output is XML/toolbar
                if output in [OutputFormat.XML, OutputFormat.TOOLBAR]:
                    try:
                        root = ET.fromstring(response.content)
                        for complete_suggestion in root.findall("CompleteSuggestion"):
                            suggestion_element = complete_suggestion.find("suggestion")
                            if suggestion_element is not None:
                                data = suggestion_element.get("data", "").lower()
                                suggestions.append(data)
                    except ET.ParseError as e:
                        logger.error(f"XML Parse Error for query '{query}': {str(e)}")
                        logger.error(f"Response Content: {response.text[:200]}...")  # Log first 200 chars
        else:
            # Try XML parsing first for toolbar/XML output formats
            try:
                root = ET.fromstring(response.content)
                for complete_suggestion in root.findall("CompleteSuggestion"):
                    suggestion_element = complete_suggestion.find("suggestion")
                    if suggestion_element is not None:
                        data = suggestion_element.get("data", "").lower()
                        suggestions.append(data)
            except ET.ParseError as e:
                logger.warning(f"XML parsing failed for query '{query}', trying JSON: {str(e)}")
                
                # Fall back to JSON parsing
                try:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                            suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                        else:
                            suggestions = [item.lower() for item in data[1]]
                except ValueError as e2:
                    logger.error(f"Both XML and JSON parsing failed for query '{query}': {str(e2)}")
                    logger.error(f"Response Content: {response.text[:200]}...")  # Log first 200 chars

    except Exception as e:
        logger.error(f"Exception in get_suggestions_for_query_async for query '{query}': {str(e)}", exc_info=True)

    return suggestions


def get_suggestions_for_query(q: str, output: OutputFormat = OutputFormat.TOOLBAR, gl: str = "US", hl: str = "en", ds: str = "", spell: int = 1) -> list:
    """
    Synchronously fetch suggestions for a given query.

    ## Core Parameters
    - **q**: Search query string (required, URL encoded)
    - **output**: Response format (toolbar, firefox, chrome, etc.)
    - **gl**: Geographic location/country (ISO country codes like US, UK)
    - **hl**: Host language (ISO language codes like en, es, fr)
    - **ds**: Data source (yt=YouTube, i=Images, n=News, etc.)
    - **spell**: Enable spell correction (0=disabled, 1=enabled)
    """
    suggestions = []
    try:
        proxy_url = get_proxy()
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        # Build parameters dictionary
        params = {
            "q": q,
            "output": output.value if isinstance(output, OutputFormat) else output,
            "gl": gl,
            "hl": hl,
            "spell": spell
        }
        
        # Add ds parameter if provided and not empty
        if ds:
            params["ds"] = ds
            
        # Make request with parameters
        response = requests.get("https://www.google.com/complete/search", params=params, proxies=proxies)

        if response.status_code != 200:
            logger.error(f"Failed to retrieve suggestions for query '{q}'. Status Code: {response.status_code}")
            return suggestions

        # Determine the actual response format based on parameters and content
        # When client parameter is specified, Google usually returns JSON regardless of output parameter
        should_try_json_first = (
            isinstance(output, str) and output.lower() in ["chrome", "firefox", "safari", "opera"] or
            isinstance(output, OutputFormat) and output in [OutputFormat.CHROME, OutputFormat.FIREFOX, OutputFormat.SAFARI, OutputFormat.OPERA]
        )
        
        # Check if response looks like JSON (starts with [ or {) or JSONP (contains callback function)
        response_text = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
        looks_like_json = response_text.strip().startswith(('[', '{')) if response_text else False
        looks_like_jsonp = "(" in response_text and response_text.endswith(")") if response_text else False
        
        # Smart response parsing - try the most likely format first, then fall back
        if should_try_json_first or looks_like_json or looks_like_jsonp:
            # Try JSON parsing first
            try:
                # Handle JSONP response (callback wrapped JSON)
                if looks_like_jsonp:
                    logger.debug(f"Detected JSONP response for query '{q}', extracting JSON data")
                    # Extract JSON data from JSONP wrapper
                    # Format is typically: callback_name({"data": "value"});
                    start_idx = response_text.find('(')
                    end_idx = response_text.rfind(')')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        json_str = response_text[start_idx + 1:end_idx]
                        data = json.loads(json_str)
                        # Process the extracted JSON data
                        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                            if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                                suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                            else:
                                suggestions = [item.lower() for item in data[1]]
                    else:
                        logger.warning(f"Failed to extract JSON from JSONP response for query '{q}'")
                else:
                    # Regular JSON response
                    data = response.json()
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                            suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                        else:
                            suggestions = [item.lower() for item in data[1]]
            except (ValueError, AttributeError) as e:
                logger.warning(f"JSON parsing failed for query '{q}', falling back to XML: {str(e)}")
                
                # Only fall back to XML if output is XML/toolbar
                if (isinstance(output, str) and output.lower() in ["toolbar", "xml"]) or (
                    isinstance(output, OutputFormat) and output in [OutputFormat.XML, OutputFormat.TOOLBAR]
                ):
                    try:
                        root = ET.fromstring(response.content)
                        for complete_suggestion in root.findall("CompleteSuggestion"):
                            suggestion_element = complete_suggestion.find("suggestion")
                            if suggestion_element is not None:
                                data = suggestion_element.get("data", "").lower()
                                suggestions.append(data)
                    except ET.ParseError as e:
                        logger.error(f"XML Parse Error for query '{q}': {str(e)}")
                        logger.error(f"Response Content: {response.text[:200] if hasattr(response, 'text') else 'No text available'}...")
        else:
            # Try XML parsing first for toolbar/XML output formats
            try:
                root = ET.fromstring(response.content)
                for complete_suggestion in root.findall("CompleteSuggestion"):
                    suggestion_element = complete_suggestion.find("suggestion")
                    if suggestion_element is not None:
                        data = suggestion_element.get("data", "").lower()
                        suggestions.append(data)
            except ET.ParseError as e:
                logger.warning(f"XML parsing failed for query '{q}', trying JSON: {str(e)}")
                
                # Fall back to JSON parsing
                try:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                        if all(isinstance(item, list) and len(item) > 0 for item in data[1]):
                            suggestions = [item[0].lower() for item in data[1] if isinstance(item, list) and len(item) > 0]
                        else:
                            suggestions = [item.lower() for item in data[1]]
                except (ValueError, AttributeError) as e2:
                    logger.error(f"Both XML and JSON parsing failed for query '{q}': {str(e2)}")
                    logger.error(f"Response Content: {response.text[:200] if hasattr(response, 'text') else 'No text available'}...")
    except Exception as e:
        logger.error(f"Exception in get_suggestions_for_query for query '{q}': {str(e)}", exc_info=True)

    return suggestions
