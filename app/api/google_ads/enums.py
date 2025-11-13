"""
Enums for Google Ads API parameters.

This module defines enumerations for various Google Ads API parameters,
making it easier to work with predefined values.
"""

from enum import Enum


class KeywordMatchType(str, Enum):
    """Keyword match types for Google Ads."""
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


class CompetitionLevel(str, Enum):
    """Competition level for keywords."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNSPECIFIED = "UNSPECIFIED"


class KeywordPlanNetwork(str, Enum):
    """Network for keyword planning."""
    GOOGLE_SEARCH = "GOOGLE_SEARCH"
    GOOGLE_SEARCH_AND_PARTNERS = "GOOGLE_SEARCH_AND_PARTNERS"


class CampaignStatus(str, Enum):
    """Campaign status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class AdGroupStatus(str, Enum):
    """Ad group status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class AdStatus(str, Enum):
    """Ad status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class DeviceType(str, Enum):
    """Device types for targeting and reporting."""
    MOBILE = "MOBILE"
    DESKTOP = "DESKTOP"
    TABLET = "TABLET"
    CONNECTED_TV = "CONNECTED_TV"


class MetricType(str, Enum):
    """Available metric types for reporting."""
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    COST = "cost_micros"
    CONVERSIONS = "conversions"
    CONVERSION_VALUE = "conversion_value"
    CTR = "ctr"
    AVERAGE_CPC = "average_cpc"
    AVERAGE_CPM = "average_cpm"
    AVERAGE_POSITION = "average_position"


class DateRangeType(str, Enum):
    """Predefined date ranges for reporting."""
    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_14_DAYS = "LAST_14_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_BUSINESS_WEEK = "LAST_BUSINESS_WEEK"
    LAST_WEEK_SUN_SAT = "LAST_WEEK_SUN_SAT"
    LAST_WEEK_MON_SUN = "LAST_WEEK_MON_SUN"
    THIS_MONTH = "THIS_MONTH"
    LAST_MONTH = "LAST_MONTH"
    ALL_TIME = "ALL_TIME"


class LanguageCode(str, Enum):
    """Common language codes for targeting."""
    ENGLISH = "1000"  # English
    SPANISH = "1003"  # Spanish
    FRENCH = "1002"  # French
    GERMAN = "1001"  # German
    ITALIAN = "1004"  # Italian
    PORTUGUESE = "1014"  # Portuguese
    RUSSIAN = "1019"  # Russian
    JAPANESE = "1005"  # Japanese
    CHINESE_SIMPLIFIED = "1017"  # Chinese (Simplified)
    CHINESE_TRADITIONAL = "1018"  # Chinese (Traditional)
    KOREAN = "1012"  # Korean
    ARABIC = "1019"  # Arabic
    DUTCH = "1010"  # Dutch
    HINDI = "1023"  # Hindi


class LocationType(str, Enum):
    """Location types for geographic targeting."""
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    CITY = "CITY"
    POSTAL_CODE = "POSTAL_CODE"
    DMA_REGION = "DMA_REGION"  # Designated Market Area (US TV markets)


class SortOrder(str, Enum):
    """Sort order for result sets."""
    ASC = "ASC"
    DESC = "DESC"


class KeywordIdeaSource(str, Enum):
    """Sources for keyword idea generation."""
    SEED_KEYWORDS = "SEED"  # User-provided seed keywords
    URL = "URL"  # Extract keywords from URL
    COMPETITOR_URL = "COMPETITOR"  # Competitor URL analysis


class ForecastPeriod(str, Enum):
    """Time periods for keyword forecasts."""
    NEXT_7_DAYS = "NEXT_7_DAYS"
    NEXT_14_DAYS = "NEXT_14_DAYS"
    NEXT_30_DAYS = "NEXT_30_DAYS"
    NEXT_90_DAYS = "NEXT_90_DAYS"


class TargetingDimension(str, Enum):
    """Dimensions for targeting criteria."""
    KEYWORD = "KEYWORD"
    LOCATION = "LOCATION"
    LANGUAGE = "LANGUAGE"
    DEVICE = "DEVICE"
    AD_SCHEDULE = "AD_SCHEDULE"
    AGE_RANGE = "AGE_RANGE"
    GENDER = "GENDER"
    INCOME_RANGE = "INCOME_RANGE"
    PARENTAL_STATUS = "PARENTAL_STATUS"


class BidStrategy(str, Enum):
    """Bidding strategies."""
    MANUAL_CPC = "MANUAL_CPC"
    MAXIMIZE_CLICKS = "MAXIMIZE_CLICKS"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    TARGET_CPA = "TARGET_CPA"
    TARGET_ROAS = "TARGET_ROAS"
    TARGET_IMPRESSION_SHARE = "TARGET_IMPRESSION_SHARE"
    TARGET_SPEND = "TARGET_SPEND"
