import os
from contextlib import asynccontextmanager

import nltk
from fastapi import FastAPI

# Import version from version file
try:
    from app.__version__ import __version__ as app_version
except ImportError:
    app_version = "1.0.0"  # Fallback version


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Download required NLTK data on startup
    try:
        # Set NLTK data path to a writable directory
        nltk_data_dir = os.path.join(os.getcwd(), "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        nltk.data.path.insert(0, nltk_data_dir)

        # Download required NLTK resources
        nltk.download("punkt_tab", download_dir=nltk_data_dir, quiet=True)
        logger.info("NLTK resources downloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to download NLTK resources: {e}")

    yield


# Update FastAPI app initialization
app = FastAPI(
    title="Social Flood API",
    description="API for social media monitoring and content analysis",
    version=app_version,  # Use dynamic version
    lifespan=lifespan,
)
