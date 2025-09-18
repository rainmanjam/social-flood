"""
Example usage of the BaseRouter class.

This file demonstrates how to use the BaseRouter class in different scenarios.
It is not meant to be imported or used directly in the application.
"""

from typing import List, Optional

from fastapi import Depends, Query
from pydantic import BaseModel

from app.core.base_router import BaseRouter

# Example 1: Basic usage with auto-derived service_name
news_router = BaseRouter(prefix="/google-news")
# service_name is automatically derived as "google-news"

# Example 2: Explicit service_name
youtube_router = BaseRouter(
    prefix="/youtube-transcripts", service_name="YouTube Transcripts API"  # Override the auto-derived name
)

# Example 3: With custom responses
trends_router = BaseRouter(
    prefix="/google-trends",
    responses={
        400: {
            "description": "Invalid trend parameters",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://socialflood.com/problems/validation_error",
                        "title": "Invalid Parameters",
                        "status": 400,
                        "detail": "The provided trend parameters are invalid",
                        "invalid_fields": ["geo", "date"],
                    }
                }
            },
        },
        404: {
            "description": "Trend data not found",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://socialflood.com/problems/not_found",
                        "title": "Not Found",
                        "status": 404,
                        "detail": "No trend data found for the specified query",
                    }
                }
            },
        },
    },
)


# Example models for the API endpoints
class NewsArticle(BaseModel):
    id: str
    title: str
    source: str
    published_date: str


class NewsArticleCreate(BaseModel):
    title: str
    source: str
    published_date: str


# Example endpoints using the router
@news_router.get("/articles/", response_model=List[NewsArticle])
async def list_articles(source: Optional[str] = Query(None, description="Filter by news source")):
    """
    List all news articles, optionally filtered by source.
    """
    # Example implementation
    articles = [
        {"id": "1", "title": "AI Breakthrough", "source": "Tech News", "published_date": "2023-06-01"},
        {"id": "2", "title": "Market Update", "source": "Finance Daily", "published_date": "2023-06-02"},
    ]

    if source:
        articles = [a for a in articles if a["source"] == source]

    return articles


@news_router.get("/articles/{article_id}", response_model=NewsArticle)
async def get_article(article_id: str):
    """
    Get details of a specific news article.
    """
    # Example of using the error handling methods
    if article_id != "1" and article_id != "2":
        news_router.raise_not_found_error("Article", article_id)

    # Example implementation
    articles = {
        "1": {"id": "1", "title": "AI Breakthrough", "source": "Tech News", "published_date": "2023-06-01"},
        "2": {"id": "2", "title": "Market Update", "source": "Finance Daily", "published_date": "2023-06-02"},
    }

    return articles[article_id]


@news_router.post("/articles/", response_model=NewsArticle, status_code=201)
async def create_article(article: NewsArticleCreate):
    """
    Create a new news article.
    """
    # Example of validation error
    if not article.title:
        news_router.raise_validation_error("Title cannot be empty", field="title")

    # Example implementation
    new_article = {"id": "3", **article.dict()}

    return new_article


# Example of how to use the router in FastAPI app
"""
# In your main.py:

from app.core.base_router_example import news_router

app = FastAPI()

# Include the router - note we call the router instance to get the underlying APIRouter
app.include_router(news_router())
"""
