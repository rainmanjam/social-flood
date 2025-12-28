"""
Central enum definitions for the Social Flood API.

This module consolidates all enums used across different API endpoints
to prevent duplication and ensure consistency.
"""
from enum import Enum, IntEnum


# =============================================================================
# Google Trends Enums
# =============================================================================

class TimeframeEnum(IntEnum):
    """Timeframe integer values for Google Trends."""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class HumanFriendlyBatchPeriod(str, Enum):
    """Human-readable batch period options for Google Trends."""
    PAST_4H = "past_4h"
    PAST_24H = "past_24h"
    PAST_48H = "past_48h"
    PAST_7D = "past_7d"


class StandardTimeframe(str, Enum):
    """Standard timeframe options for Google Trends."""
    NOW_1H = "now 1-H"
    NOW_4H = "now 4-H"
    TODAY_1M = "today 1-m"
    TODAY_3M = "today 3-m"
    TODAY_12M = "today 12-m"


class CustomIntervalTimeframe(str, Enum):
    """Custom interval timeframe options for Google Trends."""
    NOW_123H = "now 123-H"
    NOW_72H = "now 72-H"
    TODAY_45D = "today 45-d"
    TODAY_90D = "today 90-d"
    TODAY_18M = "today 18-m"


# =============================================================================
# Google Autocomplete Enums
# =============================================================================

class OutputFormat(str, Enum):
    """Output format options for Google Autocomplete API."""
    TOOLBAR = "toolbar"  # XML format used by Google Toolbar
    CHROME = "chrome"    # JSON format used by Chrome browser
    FIREFOX = "firefox"  # JSON format used by Firefox browser
    XML = "xml"          # Standard XML format (same as toolbar)
    SAFARI = "safari"    # JSON format used by Safari browser
    OPERA = "opera"      # JSON format used by Opera browser


class ClientType(str, Enum):
    """Client identifier options for Google Autocomplete API."""
    FIREFOX = "firefox"
    CHROME = "chrome"
    SAFARI = "safari"
    OPERA = "opera"


class DataSource(str, Enum):
    """Data source options for the 'ds' parameter in Google Autocomplete."""
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


class SafeSearch(str, Enum):
    """SafeSearch content filtering options."""
    ACTIVE = "active"    # Filter explicit content
    OFF = "off"          # Show all content (no filtering)


class SearchClient(str, Enum):
    """Search client identifier options."""
    GWS_WIZ = "gws-wiz"              # Google Homepage
    GWS_WIZ_LOCAL = "gws-wiz-local"  # Google Local searches
    PSY_AB = "psy-ab"                # Chrome on Google.com
