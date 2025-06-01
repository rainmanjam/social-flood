"""
Example usage of the BaseRouter class.

This file demonstrates how to use the BaseRouter class in different scenarios.
It is not meant to be imported or used directly in the application.
"""

from fastapi import Depends, Query
from typing import List, Optional
from pydantic import BaseModel

from app.core.base_router import BaseRouter

# Example 1: Basic usage with auto-derived service_name
google_ads_router = BaseRouter(prefix="/google-ads")
# service_name is automatically derived as "google-ads"

# Example 2: Explicit service_name
youtube_router = BaseRouter(
    prefix="/youtube-transcripts",
    service_name="YouTube Transcripts API"  # Override the auto-derived name
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
                        "invalid_fields": ["geo", "date"]
                    }
                }
            }
        },
        404: {
            "description": "Trend data not found",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://socialflood.com/problems/not_found",
                        "title": "Not Found",
                        "status": 404,
                        "detail": "No trend data found for the specified query"
                    }
                }
            }
        }
    }
)

# Example models for the API endpoints
class AdCampaign(BaseModel):
    id: str
    name: str
    budget: float
    status: str

class AdCampaignCreate(BaseModel):
    name: str
    budget: float
    status: str = "DRAFT"

# Example endpoints using the router
@google_ads_router.get("/campaigns/", response_model=List[AdCampaign])
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by campaign status")
):
    """
    List all ad campaigns, optionally filtered by status.
    """
    # Example implementation
    campaigns = [
        {"id": "1", "name": "Summer Sale", "budget": 1000.0, "status": "ACTIVE"},
        {"id": "2", "name": "Holiday Promo", "budget": 2000.0, "status": "DRAFT"}
    ]
    
    if status:
        campaigns = [c for c in campaigns if c["status"] == status]
        
    return campaigns

@google_ads_router.get("/campaigns/{campaign_id}", response_model=AdCampaign)
async def get_campaign(campaign_id: str):
    """
    Get details of a specific ad campaign.
    """
    # Example of using the error handling methods
    if campaign_id != "1" and campaign_id != "2":
        google_ads_router.raise_not_found_error("Campaign", campaign_id)
        
    # Example implementation
    campaigns = {
        "1": {"id": "1", "name": "Summer Sale", "budget": 1000.0, "status": "ACTIVE"},
        "2": {"id": "2", "name": "Holiday Promo", "budget": 2000.0, "status": "DRAFT"}
    }
    
    return campaigns[campaign_id]

@google_ads_router.post("/campaigns/", response_model=AdCampaign, status_code=201)
async def create_campaign(campaign: AdCampaignCreate):
    """
    Create a new ad campaign.
    """
    # Example of validation error
    if campaign.budget <= 0:
        google_ads_router.raise_validation_error(
            "Budget must be greater than zero",
            field="budget"
        )
        
    # Example implementation
    new_campaign = {
        "id": "3",
        **campaign.dict()
    }
    
    return new_campaign

# Example of how to use the router in FastAPI app
"""
# In your main.py:

from app.core.base_router_example import google_ads_router

app = FastAPI()

# Include the router - note we call the router instance to get the underlying APIRouter
app.include_router(google_ads_router())
"""
