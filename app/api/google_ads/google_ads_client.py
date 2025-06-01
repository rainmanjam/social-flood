"""
Google Ads API client for the Social Flood API.

This module provides a client for interacting with the Google Ads API,
including authentication, error handling, and common operations.
"""
from typing import Dict, List, Optional, Any, Union
import logging
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from app.core.config import get_settings
from app.core.proxy import get_proxy

# Configure logging
logger = logging.getLogger(__name__)

class GoogleAdsClientError(Exception):
    """Exception raised for Google Ads API client errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class GoogleAdsClientManager:
    """
    Manager for Google Ads API client.
    
    This class handles authentication, client creation, and common operations
    for the Google Ads API.
    """
    
    def __init__(self):
        """Initialize the Google Ads client manager."""
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Initialize the Google Ads API client.
        
        This method creates a new Google Ads API client using the credentials
        from the application settings.
        
        Raises:
            GoogleAdsClientError: If the client cannot be initialized
        """
        try:
            # Check if all required credentials are available
            if not all([
                self.settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                self.settings.GOOGLE_ADS_CLIENT_ID,
                self.settings.GOOGLE_ADS_CLIENT_SECRET,
                self.settings.GOOGLE_ADS_REFRESH_TOKEN
            ]):
                logger.warning("Google Ads API credentials not fully configured")
                return
            
            # Create credentials dictionary
            credentials = {
                "developer_token": self.settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": self.settings.GOOGLE_ADS_CLIENT_ID,
                "client_secret": self.settings.GOOGLE_ADS_CLIENT_SECRET,
                "refresh_token": self.settings.GOOGLE_ADS_REFRESH_TOKEN,
                "use_proto_plus": True
            }
            
            # Add proxy settings if enabled
            if self.settings.ENABLE_PROXY:
                proxy_url = get_proxy()
                if proxy_url:
                    credentials["proxy"] = proxy_url
            
            # Initialize Google Ads client
            self.client = GoogleAdsClient.load_from_dict(credentials)
            logger.info("Google Ads API client initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads API client: {str(e)}")
            raise GoogleAdsClientError(
                message="Failed to initialize Google Ads API client",
                details={"error": str(e)}
            )
    
    def get_client(self) -> GoogleAdsClient:
        """
        Get the Google Ads API client.
        
        Returns:
            GoogleAdsClient: The Google Ads API client
            
        Raises:
            GoogleAdsClientError: If the client is not initialized
        """
        if not self.client:
            raise GoogleAdsClientError(
                message="Google Ads API client not initialized",
                details={"hint": "Check your Google Ads API credentials"}
            )
        return self.client
    
    def get_keyword_ideas(
        self,
        customer_id: str,
        keywords: List[str],
        language_id: Optional[str] = None,
        country_code: Optional[str] = None,
        page_url: Optional[str] = None,
        include_adult_keywords: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get keyword ideas from the Google Ads API.
        
        Args:
            customer_id: The Google Ads customer ID
            keywords: List of seed keywords
            language_id: Optional language ID (e.g., 1000 for English)
            country_code: Optional country code (e.g., US)
            page_url: Optional URL to use as seed
            include_adult_keywords: Whether to include adult keywords
            
        Returns:
            List of keyword ideas with metrics
            
        Raises:
            GoogleAdsClientError: If the request fails
        """
        try:
            client = self.get_client()
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            
            # Create request parameters
            request = client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = customer_id
            
            # Set keyword seed
            if keywords:
                keyword_seed = client.get_type("KeywordSeed")
                for keyword in keywords:
                    keyword_seed.keywords.append(keyword)
                request.keyword_seed = keyword_seed
            
            # Set URL seed if provided
            if page_url:
                url_seed = client.get_type("UrlSeed")
                url_seed.url = page_url
                request.url_seed = url_seed
            
            # Set language ID if provided
            if language_id:
                request.language = language_id
            
            # Set geo target constants if country code provided
            if country_code:
                geo_target_constant_service = client.get_service("GeoTargetConstantService")
                gtc_request = client.get_type("SuggestGeoTargetConstantsRequest")
                gtc_request.locale = "en"
                gtc_request.country_code = country_code
                
                geo_targets = geo_target_constant_service.suggest_geo_target_constants(
                    request=gtc_request
                )
                
                if geo_targets.geo_target_constant_suggestions:
                    first_suggestion = geo_targets.geo_target_constant_suggestions[0]
                    request.geo_target_constants.append(first_suggestion.geo_target_constant.resource_name)
            
            # Set keyword plan network
            request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
            
            # Execute the request
            response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
            
            # Process the results
            keyword_ideas = []
            for idea in response.results:
                keyword_idea = {
                    "text": idea.text,
                    "avg_monthly_searches": idea.keyword_idea_metrics.avg_monthly_searches,
                    "competition": str(idea.keyword_idea_metrics.competition).split(".")[-1],
                    "competition_index": idea.keyword_idea_metrics.competition_index,
                    "low_top_of_page_bid_micros": idea.keyword_idea_metrics.low_top_of_page_bid_micros / 1000000,
                    "high_top_of_page_bid_micros": idea.keyword_idea_metrics.high_top_of_page_bid_micros / 1000000,
                    "historical_metrics": {
                        "monthly_search_volumes": [
                            {
                                "year": volume.year,
                                "month": volume.month,
                                "monthly_searches": volume.monthly_searches
                            }
                            for volume in idea.keyword_idea_metrics.monthly_search_volumes
                        ]
                    }
                }
                keyword_ideas.append(keyword_idea)
            
            return keyword_ideas
        
        except GoogleAdsException as ex:
            error_details = []
            for error in ex.failure.errors:
                error_details.append({
                    "error_code": error.error_code.name,
                    "message": error.message,
                    "location": {
                        "field_path": error.location.field_path,
                        "field_name": error.location.field_name
                    }
                })
            
            raise GoogleAdsClientError(
                message="Google Ads API request failed",
                details={"errors": error_details}
            )
        
        except Exception as e:
            raise GoogleAdsClientError(
                message="Failed to get keyword ideas",
                details={"error": str(e)}
            )
    
    def get_search_volume(
        self,
        customer_id: str,
        keywords: List[str],
        language_id: Optional[str] = None,
        country_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get search volume data for specific keywords.
        
        Args:
            customer_id: The Google Ads customer ID
            keywords: List of keywords to get search volume for
            language_id: Optional language ID (e.g., 1000 for English)
            country_code: Optional country code (e.g., US)
            
        Returns:
            List of keywords with search volume data
            
        Raises:
            GoogleAdsClientError: If the request fails
        """
        try:
            client = self.get_client()
            keyword_plan_service = client.get_service("KeywordPlanService")
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            
            # Create a keyword plan
            keyword_plan = client.get_type("KeywordPlan")
            keyword_plan.name = f"Search Volume Plan {','.join(keywords)[:50]}"
            
            # Create a forecast period (next 30 days)
            forecast_period = client.get_type("KeywordPlanForecastPeriod")
            forecast_period.date_interval = client.enums.KeywordPlanForecastIntervalEnum.NEXT_30_DAYS
            keyword_plan.forecast_period = forecast_period
            
            # Create the operation
            operation = client.get_type("KeywordPlanOperation")
            operation.create = keyword_plan
            
            # Create the keyword plan
            response = keyword_plan_service.mutate_keyword_plans(
                customer_id=customer_id,
                operations=[operation]
            )
            
            # Get the keyword plan resource name
            plan_resource_name = response.results[0].resource_name
            
            # Create a keyword plan campaign
            keyword_plan_campaign = client.get_type("KeywordPlanCampaign")
            keyword_plan_campaign.name = "Search Volume Campaign"
            keyword_plan_campaign.keyword_plan = plan_resource_name
            keyword_plan_campaign.cpc_bid_micros = 1000000  # $1.00
            
            # Set the network
            keyword_plan_campaign.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
            
            # Set geo targets if country code provided
            if country_code:
                geo_target_constant_service = client.get_service("GeoTargetConstantService")
                gtc_request = client.get_type("SuggestGeoTargetConstantsRequest")
                gtc_request.locale = "en"
                gtc_request.country_code = country_code
                
                geo_targets = geo_target_constant_service.suggest_geo_target_constants(
                    request=gtc_request
                )
                
                if geo_targets.geo_target_constant_suggestions:
                    first_suggestion = geo_targets.geo_target_constant_suggestions[0]
                    geo_target = client.get_type("KeywordPlanGeoTarget")
                    geo_target.geo_target_constant = first_suggestion.geo_target_constant.resource_name
                    keyword_plan_campaign.geo_targets.append(geo_target)
            
            # Set language if provided
            if language_id:
                keyword_plan_campaign.language_constants.append(f"languageConstants/{language_id}")
            
            # Create the operation
            campaign_operation = client.get_type("KeywordPlanCampaignOperation")
            campaign_operation.create = keyword_plan_campaign
            
            # Create the keyword plan campaign
            campaign_response = client.get_service("KeywordPlanCampaignService").mutate_keyword_plan_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )
            
            # Get the keyword plan campaign resource name
            campaign_resource_name = campaign_response.results[0].resource_name
            
            # Create a keyword plan ad group
            keyword_plan_ad_group = client.get_type("KeywordPlanAdGroup")
            keyword_plan_ad_group.name = "Search Volume Ad Group"
            keyword_plan_ad_group.keyword_plan_campaign = campaign_resource_name
            keyword_plan_ad_group.cpc_bid_micros = 1000000  # $1.00
            
            # Create the operation
            ad_group_operation = client.get_type("KeywordPlanAdGroupOperation")
            ad_group_operation.create = keyword_plan_ad_group
            
            # Create the keyword plan ad group
            ad_group_response = client.get_service("KeywordPlanAdGroupService").mutate_keyword_plan_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )
            
            # Get the keyword plan ad group resource name
            ad_group_resource_name = ad_group_response.results[0].resource_name
            
            # Create keyword plan ad group keywords
            keyword_operations = []
            for keyword in keywords:
                keyword_plan_ad_group_keyword = client.get_type("KeywordPlanAdGroupKeyword")
                keyword_plan_ad_group_keyword.keyword_plan_ad_group = ad_group_resource_name
                keyword_plan_ad_group_keyword.text = keyword
                keyword_plan_ad_group_keyword.cpc_bid_micros = 1000000  # $1.00
                keyword_plan_ad_group_keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
                
                operation = client.get_type("KeywordPlanAdGroupKeywordOperation")
                operation.create = keyword_plan_ad_group_keyword
                keyword_operations.append(operation)
            
            # Create the keyword plan ad group keywords
            client.get_service("KeywordPlanAdGroupKeywordService").mutate_keyword_plan_ad_group_keywords(
                customer_id=customer_id,
                operations=keyword_operations
            )
            
            # Get the forecast
            forecast = keyword_plan_service.generate_forecast_metrics(
                keyword_plan=plan_resource_name
            )
            
            # Process the results
            keyword_metrics = []
            for campaign_forecast in forecast.campaign_forecasts:
                for ad_group_forecast in campaign_forecast.ad_group_forecasts:
                    for keyword_forecast in ad_group_forecast.keyword_forecasts:
                        keyword_metrics.append({
                            "text": keyword_forecast.keyword_plan_ad_group_keyword.split("/")[-1],
                            "impressions": keyword_forecast.keyword_forecast.impressions,
                            "clicks": keyword_forecast.keyword_forecast.clicks,
                            "cost_micros": keyword_forecast.keyword_forecast.cost_micros / 1000000,
                            "ctr": keyword_forecast.keyword_forecast.ctr,
                            "average_cpc_micros": keyword_forecast.keyword_forecast.average_cpc_micros / 1000000
                        })
            
            # Clean up by deleting the keyword plan
            delete_operation = client.get_type("KeywordPlanOperation")
            delete_operation.remove = plan_resource_name
            keyword_plan_service.mutate_keyword_plans(
                customer_id=customer_id,
                operations=[delete_operation]
            )
            
            return keyword_metrics
        
        except GoogleAdsException as ex:
            error_details = []
            for error in ex.failure.errors:
                error_details.append({
                    "error_code": error.error_code.name,
                    "message": error.message,
                    "location": {
                        "field_path": error.location.field_path,
                        "field_name": error.location.field_name
                    }
                })
            
            raise GoogleAdsClientError(
                message="Google Ads API request failed",
                details={"errors": error_details}
            )
        
        except Exception as e:
            raise GoogleAdsClientError(
                message="Failed to get search volume data",
                details={"error": str(e)}
            )
    
    def get_keyword_competition(
        self,
        customer_id: str,
        keywords: List[str],
        language_id: Optional[str] = None,
        country_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get competition metrics for specific keywords.
        
        Args:
            customer_id: The Google Ads customer ID
            keywords: List of keywords to get competition data for
            language_id: Optional language ID (e.g., 1000 for English)
            country_code: Optional country code (e.g., US)
            
        Returns:
            List of keywords with competition data
            
        Raises:
            GoogleAdsClientError: If the request fails
        """
        # This is a simplified version that uses the keyword ideas API
        # to get competition data
        return self.get_keyword_ideas(
            customer_id=customer_id,
            keywords=keywords,
            language_id=language_id,
            country_code=country_code
        )
    
    def get_bid_estimates(
        self,
        customer_id: str,
        keywords: List[str],
        language_id: Optional[str] = None,
        country_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get bid estimates for specific keywords.
        
        Args:
            customer_id: The Google Ads customer ID
            keywords: List of keywords to get bid estimates for
            language_id: Optional language ID (e.g., 1000 for English)
            country_code: Optional country code (e.g., US)
            
        Returns:
            List of keywords with bid estimates
            
        Raises:
            GoogleAdsClientError: If the request fails
        """
        # This is a simplified version that uses the keyword ideas API
        # to get bid estimates
        keyword_ideas = self.get_keyword_ideas(
            customer_id=customer_id,
            keywords=keywords,
            language_id=language_id,
            country_code=country_code
        )
        
        # Extract bid estimates
        bid_estimates = []
        for idea in keyword_ideas:
            bid_estimate = {
                "text": idea["text"],
                "low_top_of_page_bid": idea["low_top_of_page_bid_micros"],
                "high_top_of_page_bid": idea["high_top_of_page_bid_micros"],
                "competition": idea["competition"],
                "competition_index": idea["competition_index"]
            }
            bid_estimates.append(bid_estimate)
        
        return bid_estimates


# Singleton instance
google_ads_client_manager = GoogleAdsClientManager()


def get_google_ads_client() -> GoogleAdsClient:
    """
    Get the Google Ads API client.
    
    Returns:
        GoogleAdsClient: The Google Ads API client
        
    Raises:
        GoogleAdsClientError: If the client is not initialized
    """
    return google_ads_client_manager.get_client()
