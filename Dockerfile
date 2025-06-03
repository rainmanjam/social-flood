# Dockerfile
# Using an official Python image from Docker Hub (approved base image)
# Pinned to a specific version for reproducibility and security
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (for better caching)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data - update to include punkt_tab
RUN python -c "import nltk; nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt', download_dir='/usr/local/share/nltk_data')"

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create directories for NLTK and TLDExtract data with proper permissions
RUN mkdir -p /app/nltk_data /app/.tldextract_cache && \
    chown -R appuser:appuser /app/nltk_data /app/.tldextract_cache && \
    chmod 755 /app/nltk_data /app/.tldextract_cache

# Copy application code
COPY --chown=appuser:appuser . .

# Set proper permissions
RUN chmod -R 755 /app && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /usr/local/share/nltk_data && \
    chown -R appuser:appuser /usr/local/share/nltk_data

# Switch to non-root user
USER appuser

# Expose port (documentation only)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
