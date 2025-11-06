# Changelog

All notable changes to the Social Flood API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.0] - 2025-11-06

### Added

- **Python 3.13 Support**: Upgraded from Python 3.11 to Python 3.13 for improved performance
- **Modern Package Management**: Added `pyproject.toml` with comprehensive project metadata
- **Pre-commit Hooks**: Added `.pre-commit-config.yaml` with ruff, mypy, bandit, and more
- **Dependabot Configuration**: Automated dependency updates for Python, GitHub Actions, and Docker
- **Security Scanning Workflow**: Comprehensive security scanning with CodeQL, Trivy, Gitleaks, and Bandit
- **Pytest Configuration**: Added `pytest.ini` with comprehensive test configuration and markers
- **Code Quality Tools**: Added ruff (linting/formatting), mypy (type checking), bandit (security)
- **Enhanced Docker Compose**: Added v3.8 format with health checks, resource limits, and logging
- **Security Headers**: Enhanced security configuration and monitoring

### Changed

- **Dependencies**: Pinned all dependencies to specific versions for reproducibility
  - FastAPI: >=0.121.0
  - Uvicorn: >=0.38.0
  - Pydantic: >=2.12.0,<3.0.0
  - Python: 3.13
- **Docker Base Images**: Updated to latest stable versions
  - Python: 3.13-slim-bookworm
  - PostgreSQL: 17-alpine
  - Redis: 7-alpine
- **GitHub Actions**: Updated all actions to latest versions (v4/v5/v6)
- **CI/CD Pipeline**: Enhanced with security scanning, multi-version testing (3.11, 3.12, 3.13)
- **Docker Compose**: Added health checks, resource limits, restart policies, and logging configuration

### Enhanced

- **Documentation**: Improved README with badges and comprehensive project information
- **Security**: Added security.txt, enhanced security scanning, and vulnerability management
- **Testing**: Enhanced test coverage reporting and pytest configuration
- **Monitoring**: Improved metrics and observability with Prometheus integration

## [1.5.3] - 2025-10-XX

### Fixed

- Minor bug fixes and improvements
- Documentation updates

## [1.5.2] - 2025-09-XX

### Fixed

- Bug fixes and stability improvements

## [1.5.1] - 2025-08-XX

### Fixed

- Performance optimizations
- Minor bug fixes

## [1.5.0] - 2025-07-XX

### Added

- Additional features and enhancements
- Performance improvements

## [1.4.0] - 2025-06-XX

### Added

- New features and functionality
- Enhanced API capabilities

## [1.3.0] - 2025-05-XX

### Added

- Feature additions
- Improved stability

## [1.2.0] - 2025-04-XX

### Added

- New API endpoints
- Enhanced functionality

## [1.1.0] - 2025-01-15

### Added

- **Comprehensive Performance Optimizations** across all API endpoints:
  - **Caching Infrastructure**: Implemented Redis/in-memory caching with configurable TTL for all endpoints
  - **HTTP Connection Pooling**: Added shared HTTP client pools with connection limits and timeouts
  - **Concurrent Processing**: Enhanced with asyncio.gather and semaphores for parallel operations
  - **Rate Limiting**: Integrated rate limiting middleware across all API endpoints
  - **Cache Key Generation**: Added consistent cache key generation functions for all APIs
  - **Input Sanitization**: Enhanced input validation and sanitization for security

### Performance Improvements

- **Google News API**: Added caching, concurrent URL decoding, shared HTTP clients, and rate limiting
- **Google Autocomplete API**: Implemented caching, rate limiting, HTTP connection pooling, and parallel processing
- **Google Trends API**: Added caching, rate limiting, and optimized connection management for all 10 endpoints
- **YouTube Transcripts API**: Enhanced with caching, rate limiting, and connection pooling for all 5 endpoints
- **NLTK Optimization**: Improved NLTK initialization and resource management
- **HTTP Manager**: Centralized HTTP client management with connection reuse

### Technical Enhancements

- **Cache Manager**: Unified caching interface with namespace support and TTL configuration
- **Rate Limiter**: Configurable request throttling with proper dependency injection
- **HTTP Client Pools**: Optimized connection management with keep-alive and timeout handling
- **Async Utilities**: Enhanced concurrent processing with proper error handling and resource limits

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
