"""
Google Ads API client wrapper.

This module provides an async-friendly wrapper around the Google Ads API client,
following the patterns established in the Social Flood codebase.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date, timedelta
from functools import lru_cache

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GoogleAdsClientManager:
    """
    Manager class for Google Ads API client instances.

    Handles client initialization, authentication, and provides
    async-friendly wrappers for Google Ads API operations.
    """

    def __init__(
        self,
        customer_id: Optional[str] = None,
        login_customer_id: Optional[str] = None,
    ):
        """
        Initialize the Google Ads client manager.

        Args:
            customer_id: Google Ads customer ID (10 digits, no hyphens)
            login_customer_id: Login customer ID for MCC accounts (optional)
        """
        self.settings = get_settings()
        self.customer_id = customer_id or self.settings.GOOGLE_ADS_CUSTOMER_ID
        self.login_customer_id = login_customer_id or self.settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
        self._client: Optional[GoogleAdsClient] = None

        # Remove hyphens from customer IDs if present
        if self.customer_id:
            self.customer_id = self.customer_id.replace("-", "")
        if self.login_customer_id:
            self.login_customer_id = self.login_customer_id.replace("-", "")

    def _get_client_config(self) -> Dict[str, Any]:
        """
        Build the configuration dictionary for Google Ads client.

        Returns:
            Dict containing Google Ads API configuration
        """
        config = {
            "developer_token": self.settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": self.settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": self.settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": self.settings.GOOGLE_ADS_REFRESH_TOKEN,
            "use_proto_plus": self.settings.GOOGLE_ADS_USE_PROTO_PLUS,
        }

        if self.login_customer_id:
            config["login_customer_id"] = self.login_customer_id

        return config

    def get_client(self) -> GoogleAdsClient:
        """
        Get or create the Google Ads client instance.

        Returns:
            GoogleAdsClient instance

        Raises:
            ValueError: If required credentials are missing
        """
        if self._client is None:
            # Validate required credentials
            required_fields = [
                "GOOGLE_ADS_DEVELOPER_TOKEN",
                "GOOGLE_ADS_CLIENT_ID",
                "GOOGLE_ADS_CLIENT_SECRET",
                "GOOGLE_ADS_REFRESH_TOKEN",
            ]

            missing = []
            for field in required_fields:
                if not getattr(self.settings, field):
                    missing.append(field)

            if missing:
                raise ValueError(
                    f"Missing required Google Ads credentials: {', '.join(missing)}. "
                    f"Please set these in your .env file or environment variables."
                )

            if not self.customer_id and not self.settings.GOOGLE_ADS_CUSTOMER_ID:
                raise ValueError(
                    "GOOGLE_ADS_CUSTOMER_ID is required. Please set it in your .env file."
                )

            config = self._get_client_config()
            self._client = GoogleAdsClient.load_from_dict(config)
            logger.info(f"Initialized Google Ads client for customer {self.customer_id}")

        return self._client

    async def _run_in_executor(self, func, *args, **kwargs):
        """
        Run a blocking function in executor to make it async-friendly.

        Args:
            func: The function to run
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            The result of the function
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _format_customer_id(self, customer_id: Optional[str] = None) -> str:
        """
        Format customer ID for API calls (without hyphens).

        Args:
            customer_id: Customer ID to format (uses instance customer_id if None)

        Returns:
            Formatted customer ID
        """
        cid = customer_id or self.customer_id
        if not cid:
            raise ValueError("Customer ID is required")
        return cid.replace("-", "")

    async def get_keyword_ideas(
        self,
        keywords: List[str],
        language_id: str = "1000",  # English
        location_ids: Optional[List[str]] = None,
        include_adult_keywords: bool = False,
        page_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get keyword ideas and metrics from Google Ads Keyword Planner.

        Args:
            keywords: List of seed keywords
            language_id: Language ID (default: 1000 for English)
            location_ids: List of location IDs (default: None for all locations)
            include_adult_keywords: Whether to include adult keywords
            page_size: Number of results to return

        Returns:
            List of keyword ideas with metrics
        """
        def _fetch_keyword_ideas():
            try:
                client = self.get_client()
                keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
                google_ads_service = client.get_service("GoogleAdsService")

                # Build location resource names
                location_rns = []
                if location_ids:
                    for location_id in location_ids:
                        location_rns.append(
                            google_ads_service.geo_target_constant_path(location_id)
                        )
                else:
                    # Default to United States (2840)
                    location_rns.append(google_ads_service.geo_target_constant_path("2840"))

                # Build language resource name
                language_rn = google_ads_service.language_constant_path(language_id)

                # Create request
                request = client.get_type("GenerateKeywordIdeasRequest")
                request.customer_id = self._format_customer_id()
                request.language = language_rn
                request.geo_target_constants.extend(location_rns)
                request.include_adult_keywords = include_adult_keywords
                request.page_size = page_size
                request.keyword_plan_network = (
                    client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
                )

                # Add seed keywords
                request.keyword_seed.keywords.extend(keywords)

                # Execute request
                response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

                # Parse results
                results = []
                for idea in response:
                    keyword_text = idea.text
                    metrics = idea.keyword_idea_metrics

                    # Convert micros to actual currency values
                    low_bid = None
                    high_bid = None
                    if metrics.low_top_of_page_bid_micros:
                        low_bid = metrics.low_top_of_page_bid_micros / 1_000_000
                    if metrics.high_top_of_page_bid_micros:
                        high_bid = metrics.high_top_of_page_bid_micros / 1_000_000

                    # Get competition level
                    competition = None
                    competition_index = None
                    if metrics.competition:
                        competition = metrics.competition.name
                    if hasattr(metrics, 'competition_index'):
                        competition_index = metrics.competition_index

                    result = {
                        "keyword": keyword_text,
                        "avg_monthly_searches": metrics.avg_monthly_searches if metrics.avg_monthly_searches else 0,
                        "competition": competition,
                        "competition_index": competition_index,
                        "low_bid": low_bid,
                        "high_bid": high_bid,
                        "low_bid_micros": metrics.low_top_of_page_bid_micros,
                        "high_bid_micros": metrics.high_top_of_page_bid_micros,
                    }
                    results.append(result)

                logger.info(f"Retrieved {len(results)} keyword ideas for seeds: {keywords}")
                return results

            except GoogleAdsException as ex:
                logger.error(f"Google Ads API error: {ex}")
                logger.error(f"Request with ID '{ex.request_id}' failed with status '{ex.error.code().name}'")
                for error in ex.failure.errors:
                    logger.error(f"\tError: {error.message}")
                raise
            except Exception as e:
                logger.error(f"Error fetching keyword ideas: {e}", exc_info=True)
                raise

        return await self._run_in_executor(_fetch_keyword_ideas)

    async def get_keyword_metrics(
        self,
        keywords: List[str],
        language_id: str = "1000",
        location_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get metrics for specific keywords.

        This is similar to get_keyword_ideas but focuses on exact match metrics
        for the provided keywords.

        Args:
            keywords: List of keywords to get metrics for
            language_id: Language ID
            location_ids: List of location IDs

        Returns:
            List of keyword metrics
        """
        # For exact metrics, we use the same endpoint but with exact keywords
        return await self.get_keyword_ideas(
            keywords=keywords,
            language_id=language_id,
            location_ids=location_ids,
            page_size=len(keywords) * 2,  # Get some extra for variations
        )

    async def get_historical_metrics(
        self,
        keywords: List[str],
        language_id: str = "1000",
        location_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get historical search volume metrics for keywords.

        Args:
            keywords: List of keywords
            language_id: Language ID
            location_ids: List of location IDs

        Returns:
            List of historical metrics with monthly data
        """
        def _fetch_historical_metrics():
            try:
                client = self.get_client()
                keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
                google_ads_service = client.get_service("GoogleAdsService")

                # Build location resource names
                location_rns = []
                if location_ids:
                    for location_id in location_ids:
                        location_rns.append(
                            google_ads_service.geo_target_constant_path(location_id)
                        )
                else:
                    location_rns.append(google_ads_service.geo_target_constant_path("2840"))

                language_rn = google_ads_service.language_constant_path(language_id)

                # Create request
                request = client.get_type("GenerateKeywordIdeasRequest")
                request.customer_id = self._format_customer_id()
                request.language = language_rn
                request.geo_target_constants.extend(location_rns)
                request.page_size = 1000
                request.keyword_plan_network = (
                    client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
                )
                request.keyword_seed.keywords.extend(keywords)
                request.historical_metrics_options.year_month_range.start.year = (
                    datetime.now().year - 1
                )
                request.historical_metrics_options.year_month_range.start.month = (
                    datetime.now().month
                )
                request.historical_metrics_options.include_average_cpc = True

                response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

                results = []
                for idea in response:
                    metrics = idea.keyword_idea_metrics

                    monthly_volumes = []
                    if hasattr(metrics, 'monthly_search_volumes'):
                        for volume in metrics.monthly_search_volumes:
                            monthly_volumes.append({
                                "year": volume.year,
                                "month": volume.month,
                                "monthly_searches": volume.monthly_searches,
                            })

                    result = {
                        "keyword": idea.text,
                        "monthly_search_volumes": monthly_volumes,
                        "avg_monthly_searches": metrics.avg_monthly_searches,
                        "competition": metrics.competition.name if metrics.competition else None,
                    }
                    results.append(result)

                return results

            except Exception as e:
                logger.error(f"Error fetching historical metrics: {e}", exc_info=True)
                raise

        return await self._run_in_executor(_fetch_historical_metrics)

    async def get_campaigns(
        self,
        customer_id: Optional[str] = None,
        date_range: str = "LAST_30_DAYS",
    ) -> List[Dict[str, Any]]:
        """
        Get campaigns with performance metrics.

        Args:
            customer_id: Customer ID (uses instance customer_id if None)
            date_range: Date range for metrics (e.g., "LAST_30_DAYS", "LAST_7_DAYS")

        Returns:
            List of campaigns with metrics
        """
        def _fetch_campaigns():
            try:
                client = self.get_client()
                ga_service = client.get_service("GoogleAdsService")

                query = f"""
                    SELECT
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.conversions_value,
                        metrics.ctr,
                        metrics.average_cpc,
                        metrics.average_cpm
                    FROM campaign
                    WHERE segments.date DURING {date_range}
                    ORDER BY metrics.impressions DESC
                    LIMIT 1000
                """

                response = ga_service.search(
                    customer_id=self._format_customer_id(customer_id),
                    query=query
                )

                results = []
                for row in response:
                    campaign = row.campaign
                    metrics = row.metrics

                    result = {
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.name,
                        "status": campaign.status.name,
                        "impressions": metrics.impressions,
                        "clicks": metrics.clicks,
                        "cost": metrics.cost_micros / 1_000_000 if metrics.cost_micros else 0,
                        "conversions": metrics.conversions,
                        "conversion_value": metrics.conversions_value,
                        "ctr": metrics.ctr,
                        "average_cpc": metrics.average_cpc / 1_000_000 if metrics.average_cpc else 0,
                        "average_cpm": metrics.average_cpm / 1_000_000 if metrics.average_cpm else 0,
                    }
                    results.append(result)

                logger.info(f"Retrieved {len(results)} campaigns")
                return results

            except Exception as e:
                logger.error(f"Error fetching campaigns: {e}", exc_info=True)
                raise

        return await self._run_in_executor(_fetch_campaigns)

    async def get_account_info(
        self,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get Google Ads account information.

        Args:
            customer_id: Customer ID (uses instance customer_id if None)

        Returns:
            Dictionary with account information
        """
        def _fetch_account_info():
            try:
                client = self.get_client()
                ga_service = client.get_service("GoogleAdsService")

                query = """
                    SELECT
                        customer.id,
                        customer.descriptive_name,
                        customer.currency_code,
                        customer.time_zone,
                        customer.manager
                    FROM customer
                    LIMIT 1
                """

                response = ga_service.search(
                    customer_id=self._format_customer_id(customer_id),
                    query=query
                )

                for row in response:
                    customer = row.customer
                    return {
                        "customer_id": str(customer.id),
                        "descriptive_name": customer.descriptive_name,
                        "currency_code": customer.currency_code,
                        "time_zone": customer.time_zone,
                        "is_manager": customer.manager,
                    }

                return {}

            except Exception as e:
                logger.error(f"Error fetching account info: {e}", exc_info=True)
                raise

        return await self._run_in_executor(_fetch_account_info)


@lru_cache()
def get_google_ads_client_manager(
    customer_id: Optional[str] = None,
    login_customer_id: Optional[str] = None,
) -> GoogleAdsClientManager:
    """
    Get a cached Google Ads client manager instance.

    Args:
        customer_id: Customer ID
        login_customer_id: Login customer ID for MCC accounts

    Returns:
        GoogleAdsClientManager instance
    """
    return GoogleAdsClientManager(
        customer_id=customer_id,
        login_customer_id=login_customer_id,
    )
