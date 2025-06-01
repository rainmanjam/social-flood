"""
Pydantic models for the Google Ads API.

This module defines the request and response schemas for the Google Ads API endpoints.
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, HttpUrl


class KeywordIdeasRequest(BaseModel):
    """Request model for keyword ideas endpoint."""
    
    customer_id: str = Field(
        ...,
        description="Google Ads customer ID (without hyphens)",
        example="1234567890"
    )
    keywords: List[str] = Field(
        ...,
        description="List of seed keywords",
        min_items=1,
        max_items=10,
        example=["python programming", "learn python"]
    )
    language_id: Optional[str] = Field(
        None,
        description="Language ID (e.g., 1000 for English)",
        example="1000"
    )
    country_code: Optional[str] = Field(
        None,
        description="Country code (e.g., US)",
        example="US"
    )
    page_url: Optional[HttpUrl] = Field(
        None,
        description="URL to use as seed for keyword ideas",
        example="https://example.com/python-tutorial"
    )
    include_adult_keywords: bool = Field(
        False,
        description="Whether to include adult keywords"
    )


class SearchVolumeRequest(BaseModel):
    """Request model for search volume endpoint."""
    
    customer_id: str = Field(
        ...,
        description="Google Ads customer ID (without hyphens)",
        example="1234567890"
    )
    keywords: List[str] = Field(
        ...,
        description="List of keywords to get search volume for",
        min_items=1,
        max_items=20,
        example=["python programming", "learn python"]
    )
    language_id: Optional[str] = Field(
        None,
        description="Language ID (e.g., 1000 for English)",
        example="1000"
    )
    country_code: Optional[str] = Field(
        None,
        description="Country code (e.g., US)",
        example="US"
    )


class CompetitionRequest(BaseModel):
    """Request model for keyword competition endpoint."""
    
    customer_id: str = Field(
        ...,
        description="Google Ads customer ID (without hyphens)",
        example="1234567890"
    )
    keywords: List[str] = Field(
        ...,
        description="List of keywords to get competition data for",
        min_items=1,
        max_items=20,
        example=["python programming", "learn python"]
    )
    language_id: Optional[str] = Field(
        None,
        description="Language ID (e.g., 1000 for English)",
        example="1000"
    )
    country_code: Optional[str] = Field(
        None,
        description="Country code (e.g., US)",
        example="US"
    )


class BidEstimatesRequest(BaseModel):
    """Request model for bid estimates endpoint."""
    
    customer_id: str = Field(
        ...,
        description="Google Ads customer ID (without hyphens)",
        example="1234567890"
    )
    keywords: List[str] = Field(
        ...,
        description="List of keywords to get bid estimates for",
        min_items=1,
        max_items=20,
        example=["python programming", "learn python"]
    )
    language_id: Optional[str] = Field(
        None,
        description="Language ID (e.g., 1000 for English)",
        example="1000"
    )
    country_code: Optional[str] = Field(
        None,
        description="Country code (e.g., US)",
        example="US"
    )


class AutocompleteKeywordAnalysisRequest(BaseModel):
    """Request model for autocomplete keyword analysis endpoint."""
    
    customer_id: str = Field(
        ...,
        description="Google Ads customer ID (without hyphens)",
        example="1234567890"
    )
    query: str = Field(
        ...,
        description="Base query for autocomplete suggestions",
        min_length=2,
        max_length=100,
        example="python programming"
    )
    language: Optional[str] = Field(
        "en",
        description="Language code (e.g., en, fr, es)",
        example="en"
    )
    country_code: Optional[str] = Field(
        "US",
        description="Country code (e.g., US, GB, CA)",
        example="US"
    )
    language_id: Optional[str] = Field(
        None,
        description="Google Ads language ID (e.g., 1000 for English)",
        example="1000"
    )
    max_suggestions: Optional[int] = Field(
        10,
        description="Maximum number of autocomplete suggestions to analyze",
        ge=1,
        le=20,
        example=10
    )


class MonthlySearchVolume(BaseModel):
    """Model for monthly search volume data."""
    
    year: int = Field(..., description="Year", example=2025)
    month: int = Field(..., description="Month (1-12)", example=5)
    monthly_searches: int = Field(..., description="Monthly search volume", example=12000)


class HistoricalMetrics(BaseModel):
    """Model for historical metrics data."""
    
    monthly_search_volumes: List[MonthlySearchVolume] = Field(
        ...,
        description="Monthly search volume data"
    )


class KeywordIdea(BaseModel):
    """Model for keyword idea data."""
    
    text: str = Field(..., description="Keyword text", example="python programming")
    avg_monthly_searches: int = Field(..., description="Average monthly searches", example=12000)
    competition: str = Field(..., description="Competition level", example="HIGH")
    competition_index: float = Field(..., description="Competition index (0-100)", example=75.5)
    low_top_of_page_bid_micros: float = Field(..., description="Low top of page bid in USD", example=1.2)
    high_top_of_page_bid_micros: float = Field(..., description="High top of page bid in USD", example=3.5)
    historical_metrics: HistoricalMetrics = Field(..., description="Historical metrics data")


class KeywordIdeasResponse(BaseModel):
    """Response model for keyword ideas endpoint."""
    
    keyword_ideas: List[KeywordIdea] = Field(..., description="List of keyword ideas")


class SearchVolumeMetric(BaseModel):
    """Model for search volume metric data."""
    
    text: str = Field(..., description="Keyword text", example="python programming")
    impressions: float = Field(..., description="Estimated impressions", example=12000.0)
    clicks: float = Field(..., description="Estimated clicks", example=600.0)
    cost_micros: float = Field(..., description="Estimated cost in USD", example=1200.0)
    ctr: float = Field(..., description="Click-through rate", example=0.05)
    average_cpc_micros: float = Field(..., description="Average CPC in USD", example=2.0)


class SearchVolumeResponse(BaseModel):
    """Response model for search volume endpoint."""
    
    metrics: List[SearchVolumeMetric] = Field(..., description="List of search volume metrics")


class CompetitionMetric(BaseModel):
    """Model for competition metric data."""
    
    text: str = Field(..., description="Keyword text", example="python programming")
    avg_monthly_searches: int = Field(..., description="Average monthly searches", example=12000)
    competition: str = Field(..., description="Competition level", example="HIGH")
    competition_index: float = Field(..., description="Competition index (0-100)", example=75.5)
    low_top_of_page_bid_micros: float = Field(..., description="Low top of page bid in USD", example=1.2)
    high_top_of_page_bid_micros: float = Field(..., description="High top of page bid in USD", example=3.5)


class CompetitionResponse(BaseModel):
    """Response model for competition endpoint."""
    
    metrics: List[CompetitionMetric] = Field(..., description="List of competition metrics")


class BidEstimate(BaseModel):
    """Model for bid estimate data."""
    
    text: str = Field(..., description="Keyword text", example="python programming")
    low_top_of_page_bid: float = Field(..., description="Low top of page bid in USD", example=1.2)
    high_top_of_page_bid: float = Field(..., description="High top of page bid in USD", example=3.5)
    competition: str = Field(..., description="Competition level", example="HIGH")
    competition_index: float = Field(..., description="Competition index (0-100)", example=75.5)


class BidEstimatesResponse(BaseModel):
    """Response model for bid estimates endpoint."""
    
    estimates: List[BidEstimate] = Field(..., description="List of bid estimates")


class AutocompleteSuggestion(BaseModel):
    """Model for autocomplete suggestion data."""
    
    text: str = Field(..., description="Suggestion text", example="python programming tutorial")


class KeywordSEOInsight(BaseModel):
    """Model for keyword SEO insight data."""
    
    difficulty_score: Optional[int] = Field(None, description="SEO difficulty score (0-100)", example=45)
    opportunity_score: Optional[int] = Field(None, description="SEO opportunity score (0-100)", example=78)
    recommended_action: Optional[str] = Field(None, description="Recommended action", example="target")
    content_suggestions: Optional[List[str]] = Field(None, description="Content suggestions")


class AutocompleteKeywordAnalysisItem(BaseModel):
    """Model for autocomplete keyword analysis item."""
    
    keyword: str = Field(..., description="Keyword text", example="python programming tutorial")
    autocomplete_data: Dict[str, Any] = Field(..., description="Autocomplete data")
    google_ads_data: Dict[str, Any] = Field(..., description="Google Ads data")
    seo_insights: KeywordSEOInsight = Field(..., description="SEO insights")


class AutocompleteKeywordAnalysisResponse(BaseModel):
    """Response model for autocomplete keyword analysis endpoint."""
    
    query: str = Field(..., description="Original query", example="python programming")
    results: List[AutocompleteKeywordAnalysisItem] = Field(..., description="Analysis results")
