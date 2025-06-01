"""
Google Ads API endpoints for the Social Flood API.

This module provides FastAPI endpoints for accessing Google Ads API data,
including keyword research, search volume, competition analysis, and bid estimates.
It also includes an endpoint that combines Google Autocomplete with Google Ads data
for comprehensive SEO analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any, Union
import logging
import httpx
import pandas as pd
import numpy as np
from app.core.base_router import BaseRouter
from app.api.google_ads.google_ads_client import (
    get_google_ads_client,
    GoogleAdsClientManager,
    GoogleAdsClientError,
    google_ads_client_manager
)
from app.api.google_ads.models import (
    KeywordIdeasRequest,
    KeywordIdeasResponse,
    SearchVolumeRequest,
    SearchVolumeResponse,
    CompetitionRequest,
    CompetitionResponse,
    BidEstimatesRequest,
    BidEstimatesResponse,
    AutocompleteKeywordAnalysisRequest,
    AutocompleteKeywordAnalysisResponse,
    AutocompleteKeywordAnalysisItem,
    KeywordSEOInsight
)
from app.api.google_autocomplete.google_autocomplete_api import (
    get_autocomplete,
    OutputFormat,
    ClientType
)
from app.core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = BaseRouter(
    prefix="/api/v1/google-ads",
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"}
    }
)

settings = get_settings()


@router.post(
    "/keyword-ideas",
    response_model=KeywordIdeasResponse,
    summary="Get keyword ideas from Google Ads API",
    description="Retrieve keyword ideas and metrics from Google Ads API based on seed keywords",
    responses={
        200: {
            "description": "Successful response with keyword ideas",
            "content": {
                "application/json": {
                    "example": {
                        "keyword_ideas": [
                            {
                                "text": "python programming",
                                "avg_monthly_searches": 12000,
                                "competition": "HIGH",
                                "competition_index": 75.5,
                                "low_top_of_page_bid_micros": 1.2,
                                "high_top_of_page_bid_micros": 3.5,
                                "historical_metrics": {
                                    "monthly_search_volumes": [
                                        {
                                            "year": 2025,
                                            "month": 5,
                                            "monthly_searches": 12000
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_keyword_ideas(request: KeywordIdeasRequest):
    """
    Get keyword ideas from Google Ads API.
    
    This endpoint retrieves keyword ideas and metrics from Google Ads API
    based on seed keywords. It provides valuable data for keyword research
    and SEO planning.
    
    ## Request Parameters
    - **customer_id**: Google Ads customer ID (without hyphens)
    - **keywords**: List of seed keywords (1-10 keywords)
    - **language_id**: Optional language ID (e.g., 1000 for English)
    - **country_code**: Optional country code (e.g., US)
    - **page_url**: Optional URL to use as seed for keyword ideas
    - **include_adult_keywords**: Whether to include adult keywords (default: false)
    
    ## Response
    Returns a list of keyword ideas with metrics including:
    - Average monthly searches
    - Competition level
    - Competition index
    - Bid estimates
    - Historical search volume data
    """
    try:
        # Check if Google Ads API credentials are configured
        if not all([
            settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            settings.GOOGLE_ADS_CLIENT_ID,
            settings.GOOGLE_ADS_CLIENT_SECRET,
            settings.GOOGLE_ADS_REFRESH_TOKEN
        ]):
            raise HTTPException(
                status_code=503,
                detail="Google Ads API credentials not fully configured"
            )
        
        # Get keyword ideas from Google Ads API
        keyword_ideas = google_ads_client_manager.get_keyword_ideas(
            customer_id=request.customer_id,
            keywords=request.keywords,
            language_id=request.language_id,
            country_code=request.country_code,
            page_url=str(request.page_url) if request.page_url else None,
            include_adult_keywords=request.include_adult_keywords
        )
        
        # Return response
        return KeywordIdeasResponse(keyword_ideas=keyword_ideas)
    
    except GoogleAdsClientError as e:
        logger.error(f"Google Ads API error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Error in get_keyword_ideas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


@router.post(
    "/search-volume",
    response_model=SearchVolumeResponse,
    summary="Get search volume data for keywords",
    description="Retrieve search volume data for specific keywords from Google Ads API",
    responses={
        200: {
            "description": "Successful response with search volume data",
            "content": {
                "application/json": {
                    "example": {
                        "metrics": [
                            {
                                "text": "python programming",
                                "impressions": 12000.0,
                                "clicks": 600.0,
                                "cost_micros": 1200.0,
                                "ctr": 0.05,
                                "average_cpc_micros": 2.0
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_search_volume(request: SearchVolumeRequest):
    """
    Get search volume data for specific keywords.
    
    This endpoint retrieves search volume data for specific keywords from
    Google Ads API. It provides valuable data for keyword research and
    SEO planning.
    
    ## Request Parameters
    - **customer_id**: Google Ads customer ID (without hyphens)
    - **keywords**: List of keywords to get search volume for (1-20 keywords)
    - **language_id**: Optional language ID (e.g., 1000 for English)
    - **country_code**: Optional country code (e.g., US)
    
    ## Response
    Returns a list of keywords with search volume metrics including:
    - Impressions
    - Clicks
    - Cost
    - CTR (Click-Through Rate)
    - Average CPC (Cost Per Click)
    """
    try:
        # Check if Google Ads API credentials are configured
        if not all([
            settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            settings.GOOGLE_ADS_CLIENT_ID,
            settings.GOOGLE_ADS_CLIENT_SECRET,
            settings.GOOGLE_ADS_REFRESH_TOKEN
        ]):
            raise HTTPException(
                status_code=503,
                detail="Google Ads API credentials not fully configured"
            )
        
        # Get search volume data from Google Ads API
        search_volume_metrics = google_ads_client_manager.get_search_volume(
            customer_id=request.customer_id,
            keywords=request.keywords,
            language_id=request.language_id,
            country_code=request.country_code
        )
        
        # Return response
        return SearchVolumeResponse(metrics=search_volume_metrics)
    
    except GoogleAdsClientError as e:
        logger.error(f"Google Ads API error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Error in get_search_volume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


@router.post(
    "/competition",
    response_model=CompetitionResponse,
    summary="Get competition data for keywords",
    description="Retrieve competition data for specific keywords from Google Ads API",
    responses={
        200: {
            "description": "Successful response with competition data",
            "content": {
                "application/json": {
                    "example": {
                        "metrics": [
                            {
                                "text": "python programming",
                                "avg_monthly_searches": 12000,
                                "competition": "HIGH",
                                "competition_index": 75.5,
                                "low_top_of_page_bid_micros": 1.2,
                                "high_top_of_page_bid_micros": 3.5
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_competition(request: CompetitionRequest):
    """
    Get competition data for specific keywords.
    
    This endpoint retrieves competition data for specific keywords from
    Google Ads API. It provides valuable data for keyword research and
    SEO planning.
    
    ## Request Parameters
    - **customer_id**: Google Ads customer ID (without hyphens)
    - **keywords**: List of keywords to get competition data for (1-20 keywords)
    - **language_id**: Optional language ID (e.g., 1000 for English)
    - **country_code**: Optional country code (e.g., US)
    
    ## Response
    Returns a list of keywords with competition metrics including:
    - Average monthly searches
    - Competition level
    - Competition index
    - Bid estimates
    """
    try:
        # Check if Google Ads API credentials are configured
        if not all([
            settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            settings.GOOGLE_ADS_CLIENT_ID,
            settings.GOOGLE_ADS_CLIENT_SECRET,
            settings.GOOGLE_ADS_REFRESH_TOKEN
        ]):
            raise HTTPException(
                status_code=503,
                detail="Google Ads API credentials not fully configured"
            )
        
        # Get competition data from Google Ads API
        competition_metrics = google_ads_client_manager.get_keyword_competition(
            customer_id=request.customer_id,
            keywords=request.keywords,
            language_id=request.language_id,
            country_code=request.country_code
        )
        
        # Return response
        return CompetitionResponse(metrics=competition_metrics)
    
    except GoogleAdsClientError as e:
        logger.error(f"Google Ads API error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Error in get_competition: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


@router.post(
    "/bid-estimates",
    response_model=BidEstimatesResponse,
    summary="Get bid estimates for keywords",
    description="Retrieve bid estimates for specific keywords from Google Ads API",
    responses={
        200: {
            "description": "Successful response with bid estimates",
            "content": {
                "application/json": {
                    "example": {
                        "estimates": [
                            {
                                "text": "python programming",
                                "low_top_of_page_bid": 1.2,
                                "high_top_of_page_bid": 3.5,
                                "competition": "HIGH",
                                "competition_index": 75.5
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_bid_estimates(request: BidEstimatesRequest):
    """
    Get bid estimates for specific keywords.
    
    This endpoint retrieves bid estimates for specific keywords from
    Google Ads API. It provides valuable data for keyword research and
    SEO planning.
    
    ## Request Parameters
    - **customer_id**: Google Ads customer ID (without hyphens)
    - **keywords**: List of keywords to get bid estimates for (1-20 keywords)
    - **language_id**: Optional language ID (e.g., 1000 for English)
    - **country_code**: Optional country code (e.g., US)
    
    ## Response
    Returns a list of keywords with bid estimates including:
    - Low top of page bid
    - High top of page bid
    - Competition level
    - Competition index
    """
    try:
        # Check if Google Ads API credentials are configured
        if not all([
            settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            settings.GOOGLE_ADS_CLIENT_ID,
            settings.GOOGLE_ADS_CLIENT_SECRET,
            settings.GOOGLE_ADS_REFRESH_TOKEN
        ]):
            raise HTTPException(
                status_code=503,
                detail="Google Ads API credentials not fully configured"
            )
        
        # Get bid estimates from Google Ads API
        bid_estimates = google_ads_client_manager.get_bid_estimates(
            customer_id=request.customer_id,
            keywords=request.keywords,
            language_id=request.language_id,
            country_code=request.country_code
        )
        
        # Return response
        return BidEstimatesResponse(estimates=bid_estimates)
    
    except GoogleAdsClientError as e:
        logger.error(f"Google Ads API error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Error in get_bid_estimates: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


@router.post(
    "/autocomplete-keyword-analysis",
    response_model=AutocompleteKeywordAnalysisResponse,
    summary="Analyze autocomplete suggestions with Google Ads data",
    description="Retrieve and analyze Google Autocomplete suggestions with Google Ads data for comprehensive SEO insights",
    responses={
        200: {
            "description": "Successful response with autocomplete keyword analysis",
            "content": {
                "application/json": {
                    "example": {
                        "query": "python programming",
                        "results": [
                            {
                                "keyword": "python programming tutorial",
                                "autocomplete_data": {
                                    "suggestions": ["python programming tutorial for beginners", "python programming tutorial pdf"],
                                    "trending_score": 85
                                },
                                "google_ads_data": {
                                    "search_volume": {
                                        "monthly_searches": 12000,
                                        "trend": "increasing"
                                    },
                                    "competition": {
                                        "level": "medium",
                                        "competition_index": 0.65
                                    }
                                },
                                "seo_insights": {
                                    "difficulty_score": 45,
                                    "opportunity_score": 78,
                                    "recommended_action": "target",
                                    "content_suggestions": [
                                        "Create beginner-friendly tutorial series",
                                        "Develop interactive coding examples"
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def analyze_autocomplete_keywords(request: AutocompleteKeywordAnalysisRequest):
    """
    Analyze autocomplete suggestions with Google Ads data.
    
    This endpoint retrieves Google Autocomplete suggestions for a query and
    analyzes them with Google Ads data to provide comprehensive SEO insights.
    It combines the power of real-time search suggestions with historical
    search volume and competition data.
    
    ## Request Parameters
    - **customer_id**: Google Ads customer ID (without hyphens)
    - **query**: Base query for autocomplete suggestions
    - **language**: Optional language code (e.g., en, fr, es)
    - **country_code**: Optional country code (e.g., US, GB, CA)
    - **language_id**: Optional Google Ads language ID (e.g., 1000 for English)
    - **max_suggestions**: Maximum number of autocomplete suggestions to analyze (1-20)
    
    ## Response
    Returns a comprehensive analysis of autocomplete suggestions with:
    - Autocomplete data (suggestions, trending score)
    - Google Ads data (search volume, competition, bid estimates)
    - SEO insights (difficulty score, opportunity score, recommended action, content suggestions)
    """
    try:
        # Check if Google Ads API credentials are configured
        if not all([
            settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            settings.GOOGLE_ADS_CLIENT_ID,
            settings.GOOGLE_ADS_CLIENT_SECRET,
            settings.GOOGLE_ADS_REFRESH_TOKEN
        ]):
            raise HTTPException(
                status_code=503,
                detail="Google Ads API credentials not fully configured"
            )
        
        # Get autocomplete suggestions
        autocomplete_response = await get_autocomplete(
            q=request.query,
            output=OutputFormat.CHROME,
            client=ClientType.CHROME,
            gl=request.country_code,
            hl=request.language,
            variations=False
        )
        
        # Extract suggestions
        suggestions = autocomplete_response.get("suggestions", [])
        
        # Limit suggestions to max_suggestions
        suggestions = suggestions[:request.max_suggestions]
        
        if not suggestions:
            return AutocompleteKeywordAnalysisResponse(
                query=request.query,
                results=[]
            )
        
        # Get Google Ads data for suggestions
        keyword_ideas = google_ads_client_manager.get_keyword_ideas(
            customer_id=request.customer_id,
            keywords=suggestions,
            language_id=request.language_id,
            country_code=request.country_code
        )
        
        # Create a mapping of keyword to keyword idea
        keyword_idea_map = {idea["text"].lower(): idea for idea in keyword_ideas}
        
        # Generate SEO insights
        results = []
        for suggestion in suggestions:
            suggestion_lower = suggestion.lower()
            
            # Get Google Ads data for this suggestion
            google_ads_data = {}
            if suggestion_lower in keyword_idea_map:
                idea = keyword_idea_map[suggestion_lower]
                google_ads_data = {
                    "search_volume": {
                        "monthly_searches": idea["avg_monthly_searches"],
                        "trend": "increasing" if idea["avg_monthly_searches"] > 1000 else "stable",
                        "seasonal_pattern": "stable"
                    },
                    "competition": {
                        "level": idea["competition"],
                        "competition_index": idea["competition_index"],
                        "top_of_page_bid_low": idea["low_top_of_page_bid_micros"],
                        "top_of_page_bid_high": idea["high_top_of_page_bid_micros"]
                    }
                }
            
            # Generate SEO insights
            seo_insights = generate_seo_insights(suggestion, google_ads_data)
            
            # Create autocomplete data
            autocomplete_data = {
                "suggestions": [s for s in suggestions if suggestion.lower() in s.lower() and s.lower() != suggestion.lower()],
                "trending_score": calculate_trending_score(suggestion, google_ads_data)
            }
            
            # Add to results
            results.append(
                AutocompleteKeywordAnalysisItem(
                    keyword=suggestion,
                    autocomplete_data=autocomplete_data,
                    google_ads_data=google_ads_data,
                    seo_insights=seo_insights
                )
            )
        
        # Return response
        return AutocompleteKeywordAnalysisResponse(
            query=request.query,
            results=results
        )
    
    except GoogleAdsClientError as e:
        logger.error(f"Google Ads API error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error(f"Error in analyze_autocomplete_keywords: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


def generate_seo_insights(keyword: str, google_ads_data: Dict[str, Any]) -> KeywordSEOInsight:
    """
    Generate SEO insights for a keyword based on Google Ads data.
    
    Args:
        keyword: The keyword to analyze
        google_ads_data: Google Ads data for the keyword
        
    Returns:
        KeywordSEOInsight: SEO insights for the keyword
    """
    # Default values
    difficulty_score = None
    opportunity_score = None
    recommended_action = None
    content_suggestions = None
    
    # Check if we have Google Ads data
    if google_ads_data and "search_volume" in google_ads_data and "competition" in google_ads_data:
        # Extract data
        monthly_searches = google_ads_data["search_volume"].get("monthly_searches", 0)
        competition_level = google_ads_data["competition"].get("level", "UNKNOWN")
        competition_index = google_ads_data["competition"].get("competition_index", 0.5)
        
        # Calculate difficulty score (0-100)
        # Higher competition = higher difficulty
        if competition_level == "HIGH":
            difficulty_score = int(min(competition_index * 100 + 20, 100))
        elif competition_level == "MEDIUM":
            difficulty_score = int(min(competition_index * 100, 80))
        elif competition_level == "LOW":
            difficulty_score = int(min(competition_index * 100, 60))
        else:
            difficulty_score = 50  # Default
        
        # Calculate opportunity score (0-100)
        # Higher search volume + lower competition = higher opportunity
        if monthly_searches > 0:
            volume_score = min(monthly_searches / 10000 * 100, 100)  # Scale search volume
            opportunity_score = int((volume_score * 0.7) + ((100 - difficulty_score) * 0.3))
        else:
            opportunity_score = 0
        
        # Determine recommended action
        if opportunity_score >= 70:
            recommended_action = "target"
        elif opportunity_score >= 40:
            recommended_action = "consider"
        else:
            recommended_action = "ignore"
        
        # Generate content suggestions
        content_suggestions = generate_content_suggestions(keyword, monthly_searches, competition_level)
    
    # Create SEO insights
    return KeywordSEOInsight(
        difficulty_score=difficulty_score,
        opportunity_score=opportunity_score,
        recommended_action=recommended_action,
        content_suggestions=content_suggestions
    )


def generate_content_suggestions(keyword: str, monthly_searches: int, competition_level: str) -> List[str]:
    """
    Generate content suggestions for a keyword.
    
    Args:
        keyword: The keyword to generate suggestions for
        monthly_searches: Monthly search volume
        competition_level: Competition level (HIGH, MEDIUM, LOW)
        
    Returns:
        List[str]: Content suggestions
    """
    suggestions = []
    
    # Check if keyword contains certain patterns
    if "how to" in keyword.lower():
        suggestions.append(f"Create step-by-step tutorial on {keyword}")
        suggestions.append(f"Develop video guide for {keyword}")
    
    if "vs" in keyword.lower() or "versus" in keyword.lower():
        suggestions.append(f"Create comparison table for {keyword}")
        suggestions.append(f"Develop pros and cons analysis for {keyword}")
    
    if "best" in keyword.lower() or "top" in keyword.lower():
        suggestions.append(f"Create comprehensive roundup of {keyword}")
        suggestions.append(f"Develop comparison guide for {keyword}")
    
    if "tutorial" in keyword.lower() or "guide" in keyword.lower():
        suggestions.append(f"Create beginner-friendly {keyword}")
        suggestions.append(f"Develop interactive examples for {keyword}")
    
    # Add suggestions based on search volume and competition
    if monthly_searches > 5000:
        if competition_level == "HIGH":
            suggestions.append(f"Target long-tail variations of '{keyword}'")
            suggestions.append(f"Create in-depth, comprehensive content for '{keyword}'")
        elif competition_level == "MEDIUM":
            suggestions.append(f"Create comprehensive guide for '{keyword}'")
            suggestions.append(f"Develop visual content for '{keyword}'")
        else:  # LOW
            suggestions.append(f"Create authoritative content for '{keyword}'")
            suggestions.append(f"Develop multiple content formats for '{keyword}'")
    else:
        if competition_level == "LOW":
            suggestions.append(f"Create niche content for '{keyword}'")
        
    # If we still don't have suggestions, add generic ones
    if not suggestions:
        suggestions.append(f"Create comprehensive guide about '{keyword}'")
        suggestions.append(f"Develop FAQ section addressing '{keyword}'")
    
    # Limit to 5 suggestions
    return suggestions[:5]


def calculate_trending_score(keyword: str, google_ads_data: Dict[str, Any]) -> int:
    """
    Calculate trending score for a keyword based on Google Ads data.
    
    Args:
        keyword: The keyword to analyze
        google_ads_data: Google Ads data for the keyword
        
    Returns:
        int: Trending score (0-100)
    """
    # Default score
    score = 50
    
    # Check if we have Google Ads data
    if google_ads_data and "search_volume" in google_ads_data:
        # Extract data
        monthly_searches = google_ads_data["search_volume"].get("monthly_searches", 0)
        trend = google_ads_data["search_volume"].get("trend", "stable")
        
        # Adjust score based on search volume
        if monthly_searches > 10000:
            score += 20
        elif monthly_searches > 5000:
            score += 15
        elif monthly_searches > 1000:
            score += 10
        elif monthly_searches > 500:
            score += 5
        
        # Adjust score based on trend
        if trend == "increasing":
            score += 15
        elif trend == "decreasing":
            score -= 15
    
    # Ensure score is between 0 and 100
    return max(0, min(score, 100))
