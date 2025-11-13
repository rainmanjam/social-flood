"""
Google Ads API Router.

This module provides FastAPI endpoints for Google Ads API functionality including:
- Keyword research and metrics
- Campaign performance data
- Account information
- Creative combined endpoints (Ads + Trends + Autocomplete)
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import asyncio
import httpx
from datetime import datetime, date

from app.core.rate_limiter import rate_limit
from app.core.cache_manager import generate_cache_key, get_cached_or_fetch
from app.core.config import get_settings
from app.core.auth import get_api_key

from .client import GoogleAdsClientManager, get_google_ads_client_manager
from .models import (
    KeywordMetrics,
    KeywordIdea,
    KeywordMetricsResponse,
    KeywordIdeasResponse,
    CampaignsResponse,
    CampaignData,
    AccountInfo,
    KeywordOpportunity,
    KeywordOpportunitiesResponse,
    TrendingKeyword,
    ContentIdea,
    HistoricalMetrics,
    KeywordForecast,
    ErrorResponse,
)
from .enums import DateRangeType, LanguageCode, SortOrder

# Create router
google_ads_router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# Helper Functions
# ============================================================================

def check_google_ads_enabled():
    """
    Check if Google Ads API is enabled and configured.

    Raises:
        HTTPException: If Google Ads is not enabled or configured
    """
    if not settings.GOOGLE_ADS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Google Ads API is not enabled. Set GOOGLE_ADS_ENABLED=true in your environment."
        )

    if not settings.GOOGLE_ADS_DEVELOPER_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Google Ads API is not configured. Missing GOOGLE_ADS_DEVELOPER_TOKEN."
        )


def parse_keywords(keywords: str) -> List[str]:
    """
    Parse comma-separated keywords string into list.

    Args:
        keywords: Comma-separated keywords string

    Returns:
        List of keywords
    """
    return [kw.strip() for kw in keywords.split(",") if kw.strip()]


# ============================================================================
# Keyword Research Endpoints
# ============================================================================

@google_ads_router.get(
    "/keyword-ideas",
    response_model=KeywordIdeasResponse,
    summary="Get Keyword Ideas",
    description="Generate keyword ideas from seed keywords using Google Ads Keyword Planner"
)
async def get_keyword_ideas(
    keywords: str = Query(
        ...,
        description="Comma-separated seed keywords (e.g., 'python programming,web development')",
        example="python programming,machine learning"
    ),
    customer_id: Optional[str] = Query(
        None,
        description="Google Ads customer ID (uses default if not provided)"
    ),
    language_id: str = Query(
        "1000",
        description="Language ID (1000=English, 1003=Spanish, 1002=French, etc.)"
    ),
    location_ids: Optional[str] = Query(
        None,
        description="Comma-separated location IDs (2840=USA, 2826=UK, 2124=Canada, etc.)"
    ),
    page_size: int = Query(
        500,
        description="Maximum number of keyword ideas to return",
        ge=1,
        le=1000
    ),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get keyword ideas and suggestions from Google Ads Keyword Planner.

    This endpoint generates keyword suggestions based on your seed keywords,
    including search volume, competition, and CPC estimates.

    **Example Response:**
    ```json
    {
        "success": true,
        "customer_id": "1234567890",
        "seed_keywords": ["python programming"],
        "keyword_ideas": [
            {
                "keyword": "python tutorial",
                "avg_monthly_searches": 74000,
                "competition": "MEDIUM",
                "competition_index": 45,
                "low_bid": 0.85,
                "high_bid": 3.50
            }
        ],
        "total_ideas": 500
    }
    ```
    """
    try:
        check_google_ads_enabled()

        kw_list = parse_keywords(keywords)
        if not kw_list:
            raise HTTPException(status_code=400, detail="No valid keywords provided")

        loc_ids = None
        if location_ids:
            loc_ids = [lid.strip() for lid in location_ids.split(",") if lid.strip()]

        # Generate cache key
        cache_key = generate_cache_key(
            "google_ads_keyword_ideas",
            keywords=keywords,
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID,
            language_id=language_id,
            location_ids=location_ids,
            page_size=page_size
        )

        async def fetch_keyword_ideas():
            client_manager = get_google_ads_client_manager(customer_id=customer_id)

            ideas = await client_manager.get_keyword_ideas(
                keywords=kw_list,
                language_id=language_id,
                location_ids=loc_ids,
                page_size=page_size
            )

            # Convert to Pydantic models
            keyword_ideas = []
            for idea in ideas:
                keyword_ideas.append(KeywordIdea(
                    keyword=idea["keyword"],
                    avg_monthly_searches=idea["avg_monthly_searches"],
                    competition=idea["competition"],
                    competition_index=idea["competition_index"],
                    low_bid=idea["low_bid"],
                    high_bid=idea["high_bid"],
                    currency_code="USD"
                ))

            return KeywordIdeasResponse(
                success=True,
                customer_id=client_manager.customer_id,
                seed_keywords=kw_list,
                keyword_ideas=keyword_ideas,
                total_ideas=len(keyword_ideas)
            )

        return await get_cached_or_fetch(cache_key, fetch_keyword_ideas)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_keyword_ideas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@google_ads_router.get(
    "/keyword-metrics",
    response_model=KeywordMetricsResponse,
    summary="Get Keyword Metrics",
    description="Get detailed metrics for specific keywords"
)
async def get_keyword_metrics(
    keywords: str = Query(
        ...,
        description="Comma-separated keywords to analyze",
        example="python tutorial,python course,learn python"
    ),
    customer_id: Optional[str] = Query(None, description="Google Ads customer ID"),
    language_id: str = Query("1000", description="Language ID (1000=English)"),
    location_ids: Optional[str] = Query(
        None,
        description="Comma-separated location IDs (default: USA)"
    ),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get search volume, competition, and CPC data for specific keywords.

    Returns precise metrics for the exact keywords you provide, including:
    - Average monthly search volume
    - Competition level (LOW/MEDIUM/HIGH)
    - Competition index (0-100)
    - Top of page bid estimates (low and high range)
    """
    try:
        check_google_ads_enabled()

        kw_list = parse_keywords(keywords)
        if not kw_list:
            raise HTTPException(status_code=400, detail="No valid keywords provided")

        loc_ids = None
        if location_ids:
            loc_ids = [lid.strip() for lid in location_ids.split(",") if lid.strip()]

        cache_key = generate_cache_key(
            "google_ads_keyword_metrics",
            keywords=keywords,
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID,
            language_id=language_id,
            location_ids=location_ids
        )

        async def fetch_keyword_metrics():
            client_manager = get_google_ads_client_manager(customer_id=customer_id)

            metrics = await client_manager.get_keyword_metrics(
                keywords=kw_list,
                language_id=language_id,
                location_ids=loc_ids
            )

            keyword_metrics = []
            for metric in metrics:
                keyword_metrics.append(KeywordMetrics(
                    keyword=metric["keyword"],
                    avg_monthly_searches=metric["avg_monthly_searches"],
                    competition=metric["competition"],
                    competition_index=metric["competition_index"],
                    low_top_of_page_bid_micros=metric.get("low_bid_micros"),
                    high_top_of_page_bid_micros=metric.get("high_bid_micros"),
                    low_top_of_page_bid=metric["low_bid"],
                    high_top_of_page_bid=metric["high_bid"],
                    currency_code="USD"
                ))

            return KeywordMetricsResponse(
                success=True,
                customer_id=client_manager.customer_id,
                keywords=keyword_metrics,
                total_keywords=len(keyword_metrics)
            )

        return await get_cached_or_fetch(cache_key, fetch_keyword_metrics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_keyword_metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@google_ads_router.get(
    "/keyword-historical-metrics",
    summary="Get Historical Keyword Metrics",
    description="Get historical search volume data for keywords"
)
async def get_keyword_historical_metrics(
    keywords: str = Query(..., description="Comma-separated keywords"),
    customer_id: Optional[str] = Query(None, description="Google Ads customer ID"),
    language_id: str = Query("1000", description="Language ID"),
    location_ids: Optional[str] = Query(None, description="Location IDs"),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get historical search volume metrics for keywords over the past 12 months.

    Returns monthly search volume data to help identify seasonal trends.
    """
    try:
        check_google_ads_enabled()

        kw_list = parse_keywords(keywords)
        loc_ids = None
        if location_ids:
            loc_ids = [lid.strip() for lid in location_ids.split(",") if lid.strip()]

        cache_key = generate_cache_key(
            "google_ads_historical_metrics",
            keywords=keywords,
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID,
            language_id=language_id,
            location_ids=location_ids
        )

        async def fetch_historical():
            client_manager = get_google_ads_client_manager(customer_id=customer_id)
            return await client_manager.get_historical_metrics(
                keywords=kw_list,
                language_id=language_id,
                location_ids=loc_ids
            )

        return await get_cached_or_fetch(cache_key, fetch_historical)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_keyword_historical_metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Campaign Data Endpoints
# ============================================================================

@google_ads_router.get(
    "/campaigns",
    response_model=CampaignsResponse,
    summary="Get Campaigns",
    description="Retrieve campaigns with performance metrics"
)
async def get_campaigns(
    customer_id: Optional[str] = Query(None, description="Google Ads customer ID"),
    date_range: DateRangeType = Query(
        DateRangeType.LAST_30_DAYS,
        description="Date range for metrics"
    ),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get list of campaigns with performance metrics.

    Returns campaign data including:
    - Campaign ID and name
    - Status (ENABLED, PAUSED, REMOVED)
    - Performance metrics (impressions, clicks, cost, conversions)
    - Calculated metrics (CTR, average CPC, average CPM)
    """
    try:
        check_google_ads_enabled()

        cache_key = generate_cache_key(
            "google_ads_campaigns",
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID,
            date_range=date_range
        )

        async def fetch_campaigns():
            client_manager = get_google_ads_client_manager(customer_id=customer_id)

            campaigns = await client_manager.get_campaigns(
                customer_id=customer_id,
                date_range=date_range.value
            )

            campaign_data = []
            for camp in campaigns:
                campaign_data.append(CampaignData(
                    campaign_id=camp["campaign_id"],
                    campaign_name=camp["campaign_name"],
                    status=camp["status"],
                    impressions=camp["impressions"],
                    clicks=camp["clicks"],
                    cost=camp["cost"],
                    conversions=camp["conversions"],
                    conversion_value=camp["conversion_value"],
                    ctr=camp["ctr"],
                    average_cpc=camp["average_cpc"],
                    average_cpm=camp["average_cpm"],
                    currency_code="USD"
                ))

            return CampaignsResponse(
                success=True,
                customer_id=client_manager.customer_id,
                campaigns=campaign_data,
                total_campaigns=len(campaign_data),
                date_range=date_range.value
            )

        return await get_cached_or_fetch(cache_key, fetch_campaigns)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Account Information Endpoints
# ============================================================================

@google_ads_router.get(
    "/account-info",
    response_model=AccountInfo,
    summary="Get Account Information",
    description="Retrieve Google Ads account details"
)
async def get_account_info(
    customer_id: Optional[str] = Query(None, description="Google Ads customer ID"),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    Get Google Ads account information.

    Returns account details including:
    - Customer ID
    - Account name
    - Currency code
    - Time zone
    - Whether it's a manager (MCC) account
    """
    try:
        check_google_ads_enabled()

        cache_key = generate_cache_key(
            "google_ads_account_info",
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID
        )

        async def fetch_account_info():
            client_manager = get_google_ads_client_manager(customer_id=customer_id)
            info = await client_manager.get_account_info(customer_id=customer_id)

            return AccountInfo(
                customer_id=info["customer_id"],
                descriptive_name=info.get("descriptive_name"),
                currency_code=info.get("currency_code"),
                time_zone=info.get("time_zone"),
                is_manager=info.get("is_manager", False)
            )

        return await get_cached_or_fetch(cache_key, fetch_account_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_account_info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Creative Combined Endpoints (Ads + Trends + Autocomplete)
# ============================================================================

@google_ads_router.get(
    "/keyword-opportunities",
    response_model=KeywordOpportunitiesResponse,
    summary="🔥 Get Keyword Opportunities (Combined Data)",
    description="Combine Google Ads, Trends, and Autocomplete data for comprehensive keyword analysis"
)
async def get_keyword_opportunities(
    keywords: str = Query(
        ...,
        description="Seed keywords to analyze",
        example="python programming"
    ),
    customer_id: Optional[str] = Query(None, description="Google Ads customer ID"),
    include_trends: bool = Query(True, description="Include Google Trends data"),
    include_autocomplete: bool = Query(True, description="Include Autocomplete suggestions"),
    language_id: str = Query("1000", description="Language ID"),
    location_ids: Optional[str] = Query(None, description="Location IDs"),
    timeframe: str = Query("today 3-m", description="Trends timeframe"),
    api_key: str = Depends(get_api_key),
    rate_limit: None = Depends(rate_limit)
):
    """
    🚀 **CREATIVE COMBINED ENDPOINT**

    This endpoint combines data from multiple Google APIs to give you
    comprehensive keyword intelligence:

    1. **Google Ads** - Search volume, CPC, competition
    2. **Google Trends** - Trend interest and growth momentum
    3. **Google Autocomplete** - Related search suggestions

    **Perfect for:**
    - Content strategy planning
    - SEO keyword research
    - PPC campaign planning
    - Identifying trending opportunities

    **Returns:**
    - Opportunity score (0-100) based on volume, trends, and competition
    - Difficulty score for SEO/PPC
    - Commercial intent score
    - Related keywords from all sources
    """
    try:
        check_google_ads_enabled()

        kw_list = parse_keywords(keywords)
        loc_ids = None
        if location_ids:
            loc_ids = [lid.strip() for lid in location_ids.split(",") if lid.strip()]

        cache_key = generate_cache_key(
            "google_ads_keyword_opportunities",
            keywords=keywords,
            customer_id=customer_id or settings.GOOGLE_ADS_CUSTOMER_ID,
            include_trends=include_trends,
            include_autocomplete=include_autocomplete,
            timeframe=timeframe
        )

        async def fetch_opportunities():
            # Get Google Ads data
            client_manager = get_google_ads_client_manager(customer_id=customer_id)
            ads_data = await client_manager.get_keyword_ideas(
                keywords=kw_list,
                language_id=language_id,
                location_ids=loc_ids,
                page_size=100
            )

            opportunities = []

            # For each keyword from Ads API
            for ad_keyword in ads_data[:20]:  # Limit to top 20 for performance
                keyword = ad_keyword["keyword"]

                # Initialize opportunity
                opp = KeywordOpportunity(
                    keyword=keyword,
                    avg_monthly_searches=ad_keyword["avg_monthly_searches"],
                    competition=ad_keyword["competition"],
                    competition_index=ad_keyword["competition_index"],
                    cpc_low=ad_keyword["low_bid"],
                    cpc_high=ad_keyword["high_bid"]
                )

                # Fetch Trends data if requested
                if include_trends:
                    try:
                        async with httpx.AsyncClient() as http_client:
                            # Call internal Trends API
                            trends_response = await http_client.get(
                                f"http://localhost:8000/api/v1/google-trends/interest-over-time",
                                params={
                                    "keywords": keyword,
                                    "timeframe": timeframe
                                },
                                headers={"X-API-Key": api_key},
                                timeout=10.0
                            )

                            if trends_response.status_code == 200:
                                trends_data = trends_response.json()
                                if trends_data.get("data"):
                                    # Calculate trend metrics
                                    data_points = trends_data["data"]
                                    if len(data_points) > 0:
                                        values = [d.get(keyword, 0) for d in data_points if keyword in d]
                                        if values:
                                            opp.trend_interest = sum(values) / len(values)

                                            # Calculate trend growth
                                            if len(values) >= 2:
                                                recent_avg = sum(values[-3:]) / 3
                                                older_avg = sum(values[:3]) / 3
                                                if recent_avg > older_avg * 1.2:
                                                    opp.trend_growth = "rising"
                                                elif recent_avg < older_avg * 0.8:
                                                    opp.trend_growth = "declining"
                                                else:
                                                    opp.trend_growth = "stable"
                    except Exception as e:
                        logger.warning(f"Could not fetch trends for {keyword}: {e}")

                # Fetch Autocomplete suggestions if requested
                if include_autocomplete:
                    try:
                        async with httpx.AsyncClient() as http_client:
                            ac_response = await http_client.get(
                                f"http://localhost:8000/api/v1/google-autocomplete/autocomplete",
                                params={"q": keyword},
                                headers={"X-API-Key": api_key},
                                timeout=10.0
                            )

                            if ac_response.status_code == 200:
                                ac_data = ac_response.json()
                                if "suggestions" in ac_data:
                                    opp.autocomplete_suggestions = ac_data["suggestions"][:10]
                    except Exception as e:
                        logger.warning(f"Could not fetch autocomplete for {keyword}: {e}")

                # Calculate composite scores
                opp.opportunity_score = _calculate_opportunity_score(opp)
                opp.difficulty_score = _calculate_difficulty_score(opp)
                opp.commercial_intent = _calculate_commercial_intent(opp)

                opportunities.append(opp)

            # Sort by opportunity score
            opportunities.sort(key=lambda x: x.opportunity_score or 0, reverse=True)

            return KeywordOpportunitiesResponse(
                success=True,
                opportunities=opportunities,
                total_opportunities=len(opportunities),
                data_sources={
                    "google_ads": True,
                    "google_trends": include_trends,
                    "google_autocomplete": include_autocomplete
                }
            )

        return await get_cached_or_fetch(cache_key, fetch_opportunities)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_keyword_opportunities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helper Functions for Scoring
# ============================================================================

def _calculate_opportunity_score(opp: KeywordOpportunity) -> float:
    """
    Calculate overall opportunity score (0-100).

    Factors:
    - Search volume (40%)
    - Competition (30%) - lower is better
    - Trend growth (20%)
    - CPC value (10%) - higher indicates commercial value
    """
    score = 0.0

    # Search volume score (0-40 points)
    if opp.avg_monthly_searches:
        volume_score = min(40, (opp.avg_monthly_searches / 10000) * 40)
        score += volume_score

    # Competition score (0-30 points) - inverse, lower competition = higher score
    if opp.competition_index is not None:
        comp_score = 30 * (1 - (opp.competition_index / 100))
        score += comp_score

    # Trend growth score (0-20 points)
    if opp.trend_growth == "rising":
        score += 20
    elif opp.trend_growth == "stable":
        score += 10
    elif opp.trend_growth == "declining":
        score += 0

    # CPC value score (0-10 points)
    if opp.cpc_high:
        cpc_score = min(10, (opp.cpc_high / 5) * 10)
        score += cpc_score

    return round(min(100, score), 2)


def _calculate_difficulty_score(opp: KeywordOpportunity) -> float:
    """Calculate SEO/PPC difficulty score (0-100)."""
    if opp.competition_index is not None:
        return float(opp.competition_index)
    elif opp.competition == "HIGH":
        return 80.0
    elif opp.competition == "MEDIUM":
        return 50.0
    elif opp.competition == "LOW":
        return 20.0
    return 50.0


def _calculate_commercial_intent(opp: KeywordOpportunity) -> float:
    """
    Calculate commercial intent score (0-100).

    Based on CPC - higher CPC indicates higher commercial value.
    """
    if not opp.cpc_high:
        return 0.0

    # CPC ranges indicate commercial intent
    if opp.cpc_high >= 10:
        return 100.0
    elif opp.cpc_high >= 5:
        return 80.0
    elif opp.cpc_high >= 2:
        return 60.0
    elif opp.cpc_high >= 1:
        return 40.0
    elif opp.cpc_high >= 0.5:
        return 20.0
    else:
        return 10.0


# ============================================================================
# Health Check Endpoint
# ============================================================================

@google_ads_router.get(
    "/health",
    summary="Google Ads API Health Check",
    description="Check if Google Ads API is properly configured and accessible"
)
async def health_check(api_key: str = Depends(get_api_key)):
    """
    Health check endpoint to verify Google Ads API configuration.

    Returns configuration status and whether the API is accessible.
    """
    try:
        config_status = {
            "developer_token": bool(settings.GOOGLE_ADS_DEVELOPER_TOKEN),
            "client_id": bool(settings.GOOGLE_ADS_CLIENT_ID),
            "client_secret": bool(settings.GOOGLE_ADS_CLIENT_SECRET),
            "refresh_token": bool(settings.GOOGLE_ADS_REFRESH_TOKEN),
            "customer_id": bool(settings.GOOGLE_ADS_CUSTOMER_ID),
            "enabled": settings.GOOGLE_ADS_ENABLED,
        }

        all_configured = all([
            config_status["developer_token"],
            config_status["client_id"],
            config_status["client_secret"],
            config_status["refresh_token"],
            config_status["customer_id"],
        ])

        # Try to get account info if fully configured
        account_accessible = False
        if all_configured and settings.GOOGLE_ADS_ENABLED:
            try:
                client_manager = get_google_ads_client_manager()
                account_info = await client_manager.get_account_info()
                account_accessible = bool(account_info)
            except Exception as e:
                logger.warning(f"Account not accessible: {e}")

        return {
            "status": "healthy" if (all_configured and account_accessible) else "degraded",
            "google_ads_enabled": settings.GOOGLE_ADS_ENABLED,
            "configuration": config_status,
            "account_accessible": account_accessible,
            "message": "Google Ads API is properly configured" if all_configured else "Google Ads API is not fully configured"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
