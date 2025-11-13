"""
Pydantic models for Google Ads API endpoints.

This module defines request and response models for Google Ads API interactions.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime
from .enums import (
    KeywordMatchType,
    CompetitionLevel,
    KeywordPlanNetwork,
    CampaignStatus,
    DeviceType,
    DateRangeType,
    LanguageCode,
    SortOrder,
)


# ============================================================================
# Keyword Research Models
# ============================================================================

class KeywordMetrics(BaseModel):
    """Metrics for a single keyword."""
    keyword: str = Field(..., description="The keyword text")
    avg_monthly_searches: Optional[int] = Field(None, description="Average monthly search volume")
    competition: Optional[str] = Field(None, description="Competition level (LOW, MEDIUM, HIGH)")
    competition_index: Optional[int] = Field(None, description="Competition index (0-100)")
    low_top_of_page_bid_micros: Optional[int] = Field(None, description="Low range of top of page bid in micros")
    high_top_of_page_bid_micros: Optional[int] = Field(None, description="High range of top of page bid in micros")
    low_top_of_page_bid: Optional[float] = Field(None, description="Low range of top of page bid in currency")
    high_top_of_page_bid: Optional[float] = Field(None, description="High range of top of page bid in currency")
    currency_code: Optional[str] = Field(default="USD", description="Currency code")


class KeywordIdea(BaseModel):
    """A keyword idea with metrics."""
    keyword: str = Field(..., description="The keyword text")
    avg_monthly_searches: Optional[int] = Field(None, description="Average monthly search volume")
    competition: Optional[str] = Field(None, description="Competition level")
    competition_index: Optional[int] = Field(None, description="Competition index (0-100)")
    low_bid: Optional[float] = Field(None, description="Low bid estimate")
    high_bid: Optional[float] = Field(None, description="High bid estimate")
    currency_code: Optional[str] = Field(default="USD", description="Currency code")


class MonthlySearchVolume(BaseModel):
    """Monthly search volume data point."""
    year: int = Field(..., description="Year")
    month: int = Field(..., description="Month (1-12)")
    monthly_searches: int = Field(..., description="Number of searches")


class HistoricalMetrics(BaseModel):
    """Historical metrics for a keyword."""
    keyword: str = Field(..., description="The keyword")
    monthly_search_volumes: List[MonthlySearchVolume] = Field(default_factory=list, description="Monthly data")
    avg_monthly_searches: Optional[int] = Field(None, description="Average monthly searches")
    competition: Optional[str] = Field(None, description="Competition level")


class KeywordForecast(BaseModel):
    """Forecast data for a keyword."""
    keyword: str = Field(..., description="The keyword")
    clicks: Optional[int] = Field(None, description="Forecasted clicks")
    impressions: Optional[int] = Field(None, description="Forecasted impressions")
    cost: Optional[float] = Field(None, description="Forecasted cost")
    conversions: Optional[float] = Field(None, description="Forecasted conversions")
    ctr: Optional[float] = Field(None, description="Forecasted CTR")
    average_cpc: Optional[float] = Field(None, description="Forecasted average CPC")


# ============================================================================
# Campaign Models
# ============================================================================

class CampaignData(BaseModel):
    """Campaign information and metrics."""
    campaign_id: str = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    status: str = Field(..., description="Campaign status")
    impressions: Optional[int] = Field(None, description="Total impressions")
    clicks: Optional[int] = Field(None, description="Total clicks")
    cost: Optional[float] = Field(None, description="Total cost")
    conversions: Optional[float] = Field(None, description="Total conversions")
    conversion_value: Optional[float] = Field(None, description="Total conversion value")
    ctr: Optional[float] = Field(None, description="Click-through rate")
    average_cpc: Optional[float] = Field(None, description="Average cost per click")
    average_cpm: Optional[float] = Field(None, description="Average cost per thousand impressions")
    currency_code: Optional[str] = Field(default="USD", description="Currency code")


class AdGroupData(BaseModel):
    """Ad group information and metrics."""
    campaign_id: str = Field(..., description="Parent campaign ID")
    campaign_name: str = Field(..., description="Parent campaign name")
    ad_group_id: str = Field(..., description="Ad group ID")
    ad_group_name: str = Field(..., description="Ad group name")
    status: str = Field(..., description="Ad group status")
    impressions: Optional[int] = Field(None, description="Total impressions")
    clicks: Optional[int] = Field(None, description="Total clicks")
    cost: Optional[float] = Field(None, description="Total cost")
    conversions: Optional[float] = Field(None, description="Total conversions")
    ctr: Optional[float] = Field(None, description="Click-through rate")
    average_cpc: Optional[float] = Field(None, description="Average cost per click")


class AdPerformance(BaseModel):
    """Ad performance metrics."""
    campaign_name: str = Field(..., description="Campaign name")
    ad_group_name: str = Field(..., description="Ad group name")
    ad_id: str = Field(..., description="Ad ID")
    ad_type: str = Field(..., description="Ad type")
    headline: Optional[str] = Field(None, description="Ad headline")
    description: Optional[str] = Field(None, description="Ad description")
    status: str = Field(..., description="Ad status")
    impressions: Optional[int] = Field(None, description="Total impressions")
    clicks: Optional[int] = Field(None, description="Total clicks")
    cost: Optional[float] = Field(None, description="Total cost")
    conversions: Optional[float] = Field(None, description="Total conversions")
    ctr: Optional[float] = Field(None, description="Click-through rate")


class SearchTerm(BaseModel):
    """Search term report entry."""
    search_term: str = Field(..., description="The search query")
    keyword: Optional[str] = Field(None, description="Matched keyword")
    match_type: Optional[str] = Field(None, description="Match type")
    campaign_name: str = Field(..., description="Campaign name")
    ad_group_name: str = Field(..., description="Ad group name")
    impressions: int = Field(..., description="Impressions")
    clicks: int = Field(..., description="Clicks")
    cost: float = Field(..., description="Cost")
    conversions: Optional[float] = Field(None, description="Conversions")
    ctr: float = Field(..., description="CTR")


# ============================================================================
# Account Models
# ============================================================================

class AccountInfo(BaseModel):
    """Google Ads account information."""
    customer_id: str = Field(..., description="Customer ID")
    descriptive_name: Optional[str] = Field(None, description="Account name")
    currency_code: Optional[str] = Field(None, description="Currency code")
    time_zone: Optional[str] = Field(None, description="Account time zone")
    is_manager: bool = Field(default=False, description="Is this an MCC account")
    can_manage_clients: bool = Field(default=False, description="Can manage other accounts")


class AccountHierarchy(BaseModel):
    """Account hierarchy (for MCC accounts)."""
    manager_customer_id: str = Field(..., description="Manager account ID")
    client_customer_id: str = Field(..., description="Client account ID")
    client_name: Optional[str] = Field(None, description="Client account name")
    level: int = Field(..., description="Hierarchy level")
    is_hidden: bool = Field(default=False, description="Is hidden in hierarchy")


# ============================================================================
# Combined Analysis Models (Creative Endpoints)
# ============================================================================

class KeywordOpportunity(BaseModel):
    """Combined keyword opportunity analysis."""
    keyword: str = Field(..., description="The keyword")

    # From Google Ads
    avg_monthly_searches: Optional[int] = Field(None, description="Search volume")
    competition: Optional[str] = Field(None, description="Competition level")
    competition_index: Optional[int] = Field(None, description="Competition index")
    cpc_low: Optional[float] = Field(None, description="Low CPC estimate")
    cpc_high: Optional[float] = Field(None, description="High CPC estimate")

    # From Google Trends
    trend_interest: Optional[float] = Field(None, description="Current trend interest (0-100)")
    trend_growth: Optional[str] = Field(None, description="Trend growth (rising/stable/declining)")

    # From Google Autocomplete
    autocomplete_suggestions: List[str] = Field(default_factory=list, description="Related suggestions")

    # Computed scores
    opportunity_score: Optional[float] = Field(None, description="Overall opportunity score (0-100)")
    difficulty_score: Optional[float] = Field(None, description="SEO/PPC difficulty (0-100)")
    commercial_intent: Optional[float] = Field(None, description="Commercial intent score (0-100)")


class TrendingKeyword(BaseModel):
    """Trending keyword with combined metrics."""
    keyword: str = Field(..., description="The keyword")
    search_volume: Optional[int] = Field(None, description="Monthly searches")
    cpc: Optional[float] = Field(None, description="Average CPC")
    competition: Optional[str] = Field(None, description="Competition level")
    trend_score: Optional[float] = Field(None, description="Trend momentum score")
    related_topics: List[str] = Field(default_factory=list, description="Related topics")
    suggested_keywords: List[str] = Field(default_factory=list, description="Related keywords")


class ContentIdea(BaseModel):
    """Content idea based on combined data."""
    topic: str = Field(..., description="Content topic")
    primary_keyword: str = Field(..., description="Primary keyword")
    related_keywords: List[str] = Field(default_factory=list, description="Related keywords")
    search_volume: Optional[int] = Field(None, description="Total search volume")
    average_cpc: Optional[float] = Field(None, description="Average CPC")
    trend_interest: Optional[float] = Field(None, description="Trend interest")
    content_angles: List[str] = Field(default_factory=list, description="Suggested content angles")
    estimated_traffic_potential: Optional[int] = Field(None, description="Estimated monthly traffic")


# ============================================================================
# Response Models
# ============================================================================

class KeywordMetricsResponse(BaseModel):
    """Response for keyword metrics endpoint."""
    success: bool = Field(default=True, description="Success status")
    customer_id: str = Field(..., description="Customer ID used")
    keywords: List[KeywordMetrics] = Field(..., description="Keyword metrics")
    total_keywords: int = Field(..., description="Total keywords returned")
    message: Optional[str] = Field(None, description="Optional message")


class KeywordIdeasResponse(BaseModel):
    """Response for keyword ideas endpoint."""
    success: bool = Field(default=True, description="Success status")
    customer_id: str = Field(..., description="Customer ID used")
    seed_keywords: List[str] = Field(..., description="Input seed keywords")
    keyword_ideas: List[KeywordIdea] = Field(..., description="Generated keyword ideas")
    total_ideas: int = Field(..., description="Total ideas returned")
    message: Optional[str] = Field(None, description="Optional message")


class CampaignsResponse(BaseModel):
    """Response for campaigns list endpoint."""
    success: bool = Field(default=True, description="Success status")
    customer_id: str = Field(..., description="Customer ID used")
    campaigns: List[CampaignData] = Field(..., description="Campaign data")
    total_campaigns: int = Field(..., description="Total campaigns")
    date_range: Optional[str] = Field(None, description="Date range used")
    message: Optional[str] = Field(None, description="Optional message")


class KeywordOpportunitiesResponse(BaseModel):
    """Response for combined keyword opportunities endpoint."""
    success: bool = Field(default=True, description="Success status")
    opportunities: List[KeywordOpportunity] = Field(..., description="Keyword opportunities")
    total_opportunities: int = Field(..., description="Total opportunities")
    data_sources: Dict[str, bool] = Field(..., description="Which data sources were used")
    message: Optional[str] = Field(None, description="Optional message")


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = Field(default=False, description="Success status")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
