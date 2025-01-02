# main.py
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from app.api.google_news.google_news_api import gnews_router, setup_nltk
from app.core.auth import get_api_key

app = FastAPI(
    title="Social Flood",
    description="This API allows you to reference endpoints from social platforms.",
    version="1.0.0",
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
)

@app.on_event("startup")
async def on_startup():
    await setup_nltk()

# Register the routers with API key dependency
app.include_router(
    gnews_router,
    tags=["Google News API"],
    dependencies=[Depends(get_api_key)]
)

# Global exception handlers

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