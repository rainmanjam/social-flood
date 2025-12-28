"""
Google Trends Service.

This module handles all business logic for fetching and processing
Google Trends data, keeping the API router thin.
"""
import logging
import random
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import numpy as np
from trendspy import Trends, BatchPeriod

from app.core.proxy import get_proxy
from app.core.constants import USER_AGENT_LIST, REFERER_LIST
from app.schemas.enums import (
    TimeframeEnum,
    HumanFriendlyBatchPeriod,
    StandardTimeframe,
    CustomIntervalTimeframe,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Header Configuration - imported from app.core.constants
# USER_AGENT_LIST and REFERER_LIST are used for header rotation
# -------------------------------------------------------------------------


class GoogleTrendsService:
    """Service class for Google Trends operations."""

    def __init__(self):
        """Initialize the service."""
        self.referer_list = REFERER_LIST
        self.user_agent_list = USER_AGENT_LIST

    @staticmethod
    def df_to_json(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert a Pandas DataFrame to a list of dictionaries.

        Args:
            df: DataFrame to convert

        Returns:
            List of dictionaries, empty list if DataFrame is empty
        """
        if df is None or df.empty:
            return []
        return df.reset_index(drop=True).to_dict(orient='records')

    @staticmethod
    def to_jsonable(value: Any) -> Any:
        """
        Recursively convert objects to JSON-serializable types.

        Handles:
        - Pandas DataFrames -> list of dicts
        - Numpy int/float -> Python int/float
        - Numpy arrays -> lists
        - dict/list -> recursively process

        Args:
            value: Value to convert

        Returns:
            JSON-serializable value
        """
        if isinstance(value, pd.DataFrame):
            return GoogleTrendsService.df_to_json(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, dict):
            return {k: GoogleTrendsService.to_jsonable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [GoogleTrendsService.to_jsonable(x) for x in value]
        return value

    def get_random_headers(self) -> Dict[str, str]:
        """
        Generate random headers for requests.

        Selects random referer and user-agent from predefined lists.

        Returns:
            Dictionary of headers
        """
        referer = random.choice(self.referer_list)
        user_agent = random.choice(self.user_agent_list)
        return {
            "Referer": referer,
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }

    async def get_trends_instance(self) -> Trends:
        """
        Create and return a Trends instance.

        Applies proxy if configured and uses random headers.

        Returns:
            Configured Trends instance
        """
        proxy_url = await get_proxy()
        headers = self.get_random_headers()

        if proxy_url:
            logger.debug(f"TrendSpy is using proxy: {proxy_url}")
            return Trends(proxy=proxy_url, headers=headers)
        else:
            logger.debug("TrendSpy is not using any proxy.")
            return Trends(headers=headers)

    def parse_keywords(self, keywords: str) -> List[str]:
        """
        Parse comma-separated keywords string.

        Args:
            keywords: Comma-separated keywords string

        Returns:
            List of trimmed keyword strings
        """
        return [kw.strip() for kw in keywords.split(",") if kw.strip()]

    def map_batch_period(self, period: str) -> BatchPeriod:
        """
        Map human-friendly batch period to BatchPeriod enum.

        Args:
            period: Human-friendly period string

        Returns:
            BatchPeriod enum value
        """
        period_mapping = {
            "past_4h": BatchPeriod.Past4H,
            "past_24h": BatchPeriod.Past24H,
            "past_48h": BatchPeriod.Past48H,
            "past_7d": BatchPeriod.Past7D,
        }
        return period_mapping.get(period, BatchPeriod.Past24H)

    def build_date_range_timeframe(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> str:
        """
        Build timeframe string from date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (optional)

        Returns:
            Timeframe string for Google Trends API
        """
        if end_date:
            return f"{start_date} {end_date}"
        return f"{start_date} {start_date}"

    def process_interest_over_time(
        self,
        df: pd.DataFrame,
        keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Process interest over time DataFrame.

        Args:
            df: Raw DataFrame from Trends API
            keywords: List of keywords queried

        Returns:
            Processed result dictionary
        """
        if df is None or df.empty:
            return {
                "keywords": keywords,
                "data": [],
                "message": "No data available for the given parameters."
            }

        # Convert to JSON-serializable format
        data = self.to_jsonable(df)

        return {
            "keywords": keywords,
            "data": data,
            "columns": list(df.columns) if hasattr(df, 'columns') else []
        }

    def process_related_queries(
        self,
        result: Dict[str, Any],
        keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Process related queries result.

        Args:
            result: Raw result from Trends API
            keywords: List of keywords queried

        Returns:
            Processed result dictionary
        """
        if not result:
            return {
                "keywords": keywords,
                "related_queries": {},
                "message": "No related queries found."
            }

        processed = {}
        for keyword, data in result.items():
            processed[keyword] = {
                "top": self.to_jsonable(data.get("top", [])),
                "rising": self.to_jsonable(data.get("rising", []))
            }

        return {
            "keywords": keywords,
            "related_queries": processed
        }

    def process_interest_by_region(
        self,
        df: pd.DataFrame,
        keywords: List[str],
        resolution: str
    ) -> Dict[str, Any]:
        """
        Process interest by region DataFrame.

        Args:
            df: Raw DataFrame from Trends API
            keywords: List of keywords queried
            resolution: Geographic resolution used

        Returns:
            Processed result dictionary
        """
        if df is None or df.empty:
            return {
                "keywords": keywords,
                "resolution": resolution,
                "data": [],
                "message": "No regional data available."
            }

        return {
            "keywords": keywords,
            "resolution": resolution,
            "data": self.to_jsonable(df)
        }

    def process_trending_searches(
        self,
        df: pd.DataFrame,
        geo: str
    ) -> Dict[str, Any]:
        """
        Process trending searches DataFrame.

        Args:
            df: Raw DataFrame from Trends API
            geo: Geographic location code

        Returns:
            Processed result dictionary
        """
        if df is None or df.empty:
            return {
                "geo": geo,
                "trending_searches": [],
                "message": "No trending searches found."
            }

        return {
            "geo": geo,
            "trending_searches": self.to_jsonable(df)
        }

    def process_realtime_trending(
        self,
        result: Any,
        geo: str,
        category: Optional[str]
    ) -> Dict[str, Any]:
        """
        Process realtime trending result.

        Args:
            result: Raw result from Trends API
            geo: Geographic location code
            category: Category filter applied

        Returns:
            Processed result dictionary
        """
        return {
            "geo": geo,
            "category": category,
            "realtime_trending": self.to_jsonable(result)
        }


# Singleton instance for convenience
google_trends_service = GoogleTrendsService()
