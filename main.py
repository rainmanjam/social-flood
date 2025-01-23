from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException

from app.api.google_news.google_news_api import gnews_router, setup_nltk
from app.api.google_autocomplete.google_autocomplete_api import router as google_autocomplete_router
from app.api.google_trends.google_trends_api import google_trends_router
from app.api.youtube_transcripts.youtube_transcripts_api import youtube_transcripts_router
from app.core.auth import get_api_key

# Create the FastAPI app
app = FastAPI(
    title="Social Flood",
    description="This API allows you to reference endpoints from social platforms.",
    version="0.0.1",
    terms_of_service="https://socialflood.com/terms/",
    contact={
        "name": "API Support",
        "url": "https://socialflood.com/contact/",
        "email": "support@socialflood.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "http://www.apache.org/licenses/LICENSE-2.0.html",
    },
    docs_url="/docs",                     # URL for the interactive docs
    redoc_url="/redoc",                   # URL for the ReDoc docs
    openapi_url="/openapi.json",          # URL for the OpenAPI schema
    openapi_tags=[                        # Custom tags for grouping endpoints
        {
            "name": "users",
            "description": "Operations with users."
        }
    ],
    debug=True
)

# Startup event to load any dependencies or data
async def on_startup():
    await setup_nltk()

app.add_event_handler("startup", on_startup)

# Include the Google News router
app.include_router(
    gnews_router,
    prefix="/google-news",
    tags=["Google News API"],
    dependencies=[Depends(get_api_key)]
)

# Include the Google Trends router, mounted at /google-trends
app.include_router(
    google_trends_router,
    prefix="/google-trends",
    tags=["Google Trends API"],
    dependencies=[Depends(get_api_key)]
)

app.include_router(
    google_autocomplete_router,
    prefix="/google-search", 
    tags=["Google Search API"],
    dependencies=[Depends(get_api_key)]
)

app.include_router(
    youtube_transcripts_router,
    prefix="/youtube-transcripts", 
    tags=["YouTube Transcripts API"],
    dependencies=[Depends(get_api_key)]
)

# -------------------------------------------------------------------------
# Exception Handlers
# -------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )

# -------------------------------------------------------------------------
# Run the application
# -------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
