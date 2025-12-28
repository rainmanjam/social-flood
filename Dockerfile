# Dockerfile - Multi-stage build for Social Flood API
# Optimized for size, security, and caching
# Includes Playwright for Google Maps scraping

# =============================================================================
# Stage 1: Builder - Install dependencies and build assets
# =============================================================================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data to a portable location
RUN python -c "import nltk; \
    nltk.download('punkt_tab', download_dir='/opt/nltk_data'); \
    nltk.download('punkt', download_dir='/opt/nltk_data')"


# =============================================================================
# Stage 2: Production - Minimal runtime image with Playwright
# =============================================================================
FROM python:3.11-slim-bookworm AS production

# Security: Set environment variables early
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NLTK_DATA=/opt/nltk_data \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

WORKDIR /app

# Install runtime dependencies including Playwright browser deps
# Note: We need more packages for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    # Fonts for proper rendering
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/nltk_data /opt/nltk_data
ENV PATH="/opt/venv/bin:$PATH"

# Install Playwright browsers (Chromium only for smaller size)
# Do this as root before switching to appuser
RUN mkdir -p /opt/playwright-browsers && \
    playwright install chromium && \
    chmod -R 755 /opt/playwright-browsers

# Create required directories with proper permissions
RUN mkdir -p /app/.tldextract_cache && \
    chown -R appuser:appuser /app /opt/nltk_data /opt/playwright-browsers

# Copy application code
COPY --chown=appuser:appuser . .

# Set proper permissions
RUN chmod -R 755 /app

# Switch to non-root user
USER appuser

# Expose port (documentation only)
EXPOSE 8000

# Health check with proper intervals and retries
# - Start checking after 10s (start_period)
# - Check every 30s
# - Timeout after 10s
# - Mark unhealthy after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with optimized settings
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
