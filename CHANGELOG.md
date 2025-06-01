# Changelog

All notable changes to the Social Flood API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-05-31

### Added
- API versioning with `/api/v1/` prefix for all endpoints
- Comprehensive health check endpoints (`/health`, `/health/detailed`, `/ping`, `/status`)
- Configuration endpoints (`/api-config`, `/config-sources`)
- RFC7807 Problem Details for standardized error responses
- Prometheus metrics for monitoring (optional)
- Rate limiting with slowapi (optional)
- Custom OpenAPI documentation endpoints (`/api/docs`, `/api/redoc`)
- Proper startup and shutdown event handlers
- Comprehensive documentation (README, API_STRUCTURE, etc.)

### Changed
- Restructured main application with factory pattern
- Moved all API routers under versioned structure
- Updated URL paths for all endpoints
- Improved error handling with centralized exception handlers
- Enhanced middleware configuration
- Standardized router creation with BaseRouter

### Fixed
- Inconsistent naming in router tags
- Missing error handling for various scenarios
- Incomplete health checks
- Security headers configuration

## [0.2.0] - 2025-04-15

### Added
- Google Autocomplete API with comprehensive keyword variations
- YouTube Transcripts API for extracting video transcripts
- Proxy support for external API requests
- Caching layer with Redis support
- Basic health check endpoint

### Changed
- Improved error handling
- Enhanced logging configuration
- Updated dependencies

### Fixed
- Rate limiting issues
- Authentication edge cases

## [0.1.0] - 2025-03-01

### Added
- Initial release with Google News and Google Trends APIs
- Basic authentication with API keys
- Simple error handling
- Docker and Docker Compose support
- Basic documentation
