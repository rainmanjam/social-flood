"""
Services package for Social Flood API.

This package contains business logic services that handle data processing
and external API interactions, keeping the API routers thin and focused
on HTTP concerns.

Services:
    - google_news_service: Google News data extraction
    - google_trends_service: Google Trends data processing
    - google_autocomplete_service: Google Autocomplete keyword variations
    - youtube_transcripts_service: YouTube transcript fetching and formatting

Usage:
    from app.services.google_trends_service import google_trends_service
    from app.services.google_autocomplete_service import google_autocomplete_service
    from app.services.youtube_transcripts_service import youtube_transcripts_service
"""

# Lazy imports - import specific services as needed to avoid circular imports
# and missing dependency issues

__all__ = [
    "google_news_service",
    "google_trends_service",
    "google_autocomplete_service",
    "youtube_transcripts_service",
]
