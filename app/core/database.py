# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# Retrieve the DATABASE_URL from environment variables and convert to async format
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")

# Replace the standard PostgreSQL URL scheme with the async variant
# For PostgreSQL, use 'postgresql+asyncpg://'
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create the asynchronous engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for verbose SQL logging
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
)

# Create a configured "AsyncSession" class
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependency to get an asynchronous session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()