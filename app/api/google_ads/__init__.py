"""
Google Ads API module.

This module provides integration with Google Ads API for keyword research,
campaign data retrieval, and creative combined analytics.
"""

from .google_ads_api import google_ads_router
from .client import GoogleAdsClientManager, get_google_ads_client_manager
from .models import (
    KeywordMetrics,
    KeywordIdea,
    KeywordMetricsResponse,
    KeywordIdeasResponse,
    CampaignsResponse,
    KeywordOpportunity,
    KeywordOpportunitiesResponse,
)
from .enums import (
    KeywordMatchType,
    CompetitionLevel,
    DateRangeType,
    LanguageCode,
)

__all__ = [
    "google_ads_router",
    "GoogleAdsClientManager",
    "get_google_ads_client_manager",
    "KeywordMetrics",
    "KeywordIdea",
    "KeywordMetricsResponse",
    "KeywordIdeasResponse",
    "CampaignsResponse",
    "KeywordOpportunity",
    "KeywordOpportunitiesResponse",
    "KeywordMatchType",
    "CompetitionLevel",
    "DateRangeType",
    "LanguageCode",
]
