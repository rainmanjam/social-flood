# Testing Guide for Social Flood API

Complete guide for running, writing, and maintaining tests for the Social Flood API.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Coverage](#test-coverage)
6. [Continuous Integration](#continuous-integration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
# Install testing dependencies
pip install -r requirements-dev.txt

# Or just the essentials
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::test_validate_api_key
```

### Check Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# Open coverage report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_auth.py
│   ├── test_cache_manager.py
│   ├── test_rate_limiter.py
│   ├── test_input_sanitizer.py
│   └── test_utils.py
├── integration/             # Integration tests (external dependencies)
│   ├── test_google_news_api.py
│   ├── test_google_trends_api.py
│   ├── test_autocomplete_api.py
│   └── test_youtube_api.py
├── e2e/                     # End-to-end tests (full system)
│   └── test_full_workflow.py
└── performance/             # Performance benchmarks
    └── test_benchmarks.py
```

### Test Categories

We use pytest markers to categorize tests:

| Marker | Purpose | Example |
|--------|---------|---------|
| `unit` | Fast, isolated tests | `@pytest.mark.unit` |
| `integration` | Tests with external dependencies | `@pytest.mark.integration` |
| `e2e` | End-to-end system tests | `@pytest.mark.e2e` |
| `slow` | Tests that take >1 second | `@pytest.mark.slow` |
| `asyncio` | Async tests | Automatic with pytest-asyncio |
| `smoke` | Quick validation tests | `@pytest.mark.smoke` |
| `security` | Security-related tests | `@pytest.mark.security` |
| `performance` | Performance benchmarks | `@pytest.mark.performance` |

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run everything except integration tests
pytest -m "not integration"

# Run specific markers
pytest -m "unit or smoke"
```

### Advanced Options

```bash
# Run tests in parallel (faster)
pytest -n auto

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run last failed tests
pytest --lf

# Run failed tests first, then others
pytest --ff

# Run tests matching a keyword
pytest -k "auth or cache"

# Show print statements
pytest -s

# Disable warnings
pytest --disable-warnings
```

### Coverage Options

```bash
# HTML report (most detailed)
pytest --cov=app --cov-report=html

# Terminal report with missing lines
pytest --cov=app --cov-report=term-missing

# XML report (for CI/CD)
pytest --cov=app --cov-report=xml

# Multiple report formats
pytest --cov=app --cov-report=html --cov-report=term-missing --cov-report=xml

# Fail if coverage below 70%
pytest --cov=app --cov-fail-under=70
```

### Test Selection

```bash
# Run specific test file
pytest tests/unit/test_auth.py

# Run specific test class
pytest tests/unit/test_auth.py::TestAPIKeyAuth

# Run specific test function
pytest tests/unit/test_auth.py::test_validate_api_key

# Run multiple specific tests
pytest tests/unit/test_auth.py::test_validate_api_key tests/unit/test_cache.py::test_cache_set
```

---

## Writing Tests

### Test File Structure

```python
"""
Test module for [feature name]

This module tests [description of what's being tested].
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.core.feature import FeatureClass


# ============================================================================
# Fixtures (shared test data/setup)
# ============================================================================

@pytest.fixture
def sample_data():
    """Provide sample test data"""
    return {"key": "value"}


@pytest.fixture
async def async_client():
    """Provide async HTTP client for testing"""
    async with httpx.AsyncClient() as client:
        yield client


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.mark.unit
def test_simple_function():
    """Test that simple function works correctly"""
    result = simple_function("input")
    assert result == "expected_output"


@pytest.mark.unit
async def test_async_function():
    """Test that async function works correctly"""
    result = await async_function("input")
    assert result == "expected_output"


@pytest.mark.unit
def test_with_mock():
    """Test using mocks to isolate dependencies"""
    with patch('app.core.feature.external_api') as mock_api:
        mock_api.return_value = "mocked_response"
        result = function_using_api()
        assert result == "mocked_response"
        mock_api.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
async def test_with_real_dependencies():
    """Test with real external dependencies (Redis, DB, etc.)"""
    # This test will use real Redis/PostgreSQL from docker-compose
    pass


# ============================================================================
# Parametrized Tests (test multiple inputs)
# ============================================================================

@pytest.mark.parametrize("input,expected", [
    ("test1", "result1"),
    ("test2", "result2"),
    ("test3", "result3"),
])
def test_multiple_cases(input, expected):
    """Test multiple input/output combinations"""
    assert process(input) == expected


# ============================================================================
# Exception Testing
# ============================================================================

def test_raises_exception():
    """Test that function raises expected exception"""
    with pytest.raises(ValueError, match="expected error message"):
        function_that_raises()
```

### Testing FastAPI Endpoints

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.integration
def test_api_endpoint():
    """Test API endpoint returns correct response"""
    response = client.get(
        "/api/v1/google-news/search",
        params={"query": "technology"},
        headers={"x-api-key": "test_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "articles" in data
    assert isinstance(data["articles"], list)


@pytest.mark.integration
async def test_async_endpoint():
    """Test async endpoint with httpx"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/google-news/search",
            params={"query": "technology"},
            headers={"x-api-key": "test_key"}
        )
        assert response.status_code == 200
```

### Mocking External APIs

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.unit
async def test_google_news_api():
    """Test Google News API with mocked external calls"""
    
    # Mock the external API call
    with patch('app.services.google_news_service.GNews') as mock_gnews:
        # Configure mock
        mock_instance = AsyncMock()
        mock_instance.get_news.return_value = [
            {"title": "Test Article", "url": "https://example.com"}
        ]
        mock_gnews.return_value = mock_instance
        
        # Test your service
        from app.services.google_news_service import GoogleNewsService
        service = GoogleNewsService()
        results = await service.search("test query")
        
        # Assertions
        assert len(results) == 1
        assert results[0]["title"] == "Test Article"
        mock_instance.get_news.assert_called_once()
```

### Testing with Fixtures

```python
# conftest.py - shared fixtures
import pytest
from app.core.cache_manager import CacheManager

@pytest.fixture
async def cache_manager():
    """Provide cache manager instance"""
    manager = CacheManager()
    await manager.connect()
    yield manager
    await manager.disconnect()


@pytest.fixture
def api_headers():
    """Provide standard API headers"""
    return {"x-api-key": "test_key_123"}


# test_file.py - use fixtures
@pytest.mark.unit
async def test_with_fixtures(cache_manager, api_headers):
    """Test using shared fixtures"""
    await cache_manager.set("key", "value")
    assert await cache_manager.get("key") == "value"
```

### Testing Database Operations

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User

@pytest.fixture
def test_db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


@pytest.mark.integration
def test_user_creation(test_db):
    """Test creating user in database"""
    user = User(username="testuser", email="test@example.com")
    test_db.add(user)
    test_db.commit()
    
    retrieved = test_db.query(User).filter_by(username="testuser").first()
    assert retrieved is not None
    assert retrieved.email == "test@example.com"
```

---

## Test Coverage

### Coverage Goals

- **Overall Coverage:** Minimum 70%, target 80%+
- **Critical Modules:** 90%+ coverage
  - `app/core/auth.py`
  - `app/core/security.py`
  - `app/core/rate_limiter.py`
  - `app/core/cache_manager.py`

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=term-missing

# Output example:
# Name                              Stmts   Miss  Cover   Missing
# ---------------------------------------------------------------
# app/__init__.py                       2      0   100%
# app/core/auth.py                     45      5    89%   23-27
# app/core/cache_manager.py            67     12    82%   89-92, 145-150
# ---------------------------------------------------------------
# TOTAL                               456     45    90%
```

### Viewing HTML Coverage Report

```bash
# Generate HTML report
pytest --cov=app --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

The HTML report shows:
- Line-by-line coverage highlighting
- Which branches were taken
- Missing coverage areas
- Coverage trends over time

### Excluding Code from Coverage

Use `# pragma: no cover` for code that shouldn't be tested:

```python
def debug_function():  # pragma: no cover
    """Debug-only function"""
    print("Debug info")


if __name__ == "__main__":  # pragma: no cover
    run_app()
```

---

## Continuous Integration

### GitHub Actions Workflow

Our CI/CD pipeline automatically runs tests on:
- Every push to `main`, `develop`, or `feature/**` branches
- Every pull request to `main` or `develop`

### What Gets Tested

1. **Code Quality Checks**
   - Black (code formatting)
   - isort (import sorting)
   - Flake8 (style guide)
   - Pylint (code analysis)
   - MyPy (type checking)
   - Bandit (security scanning)

2. **Test Suite**
   - Unit tests (Python 3.10, 3.11, 3.12)
   - Integration tests
   - Coverage reporting

3. **Security Scanning**
   - Dependency vulnerabilities (Safety)
   - Security issues (Bandit)

4. **Docker Build**
   - Multi-architecture build (amd64, arm64)
   - Image signing with cosign

### Viewing CI Results

1. Go to your GitHub repository
2. Click "Actions" tab
3. Select a workflow run
4. View job results and logs

### Downloading Artifacts

CI uploads test results and coverage reports as artifacts:

1. Go to workflow run
2. Scroll to "Artifacts" section
3. Download:
   - Test results (JUnit XML)
   - Coverage reports (HTML)
   - Security scan reports (JSON)

---

## Best Practices

### 1. Write Tests First (TDD)

```python
# 1. Write the test first (it will fail)
def test_new_feature():
    result = new_feature("input")
    assert result == "expected"

# 2. Implement the feature (make test pass)
def new_feature(input):
    return "expected"

# 3. Refactor if needed
```

### 2. One Assertion Per Test (Guideline)

```python
# Good - focused test
def test_user_creation():
    user = create_user("john")
    assert user.name == "john"

def test_user_email():
    user = create_user("john")
    assert user.email == "john@example.com"

# Also OK - related assertions
def test_user_properties():
    user = create_user("john")
    assert user.name == "john"
    assert user.is_active is True
```

### 3. Use Descriptive Test Names

```python
# Bad
def test_1():
    pass

# Good
def test_user_login_with_valid_credentials_returns_token():
    pass

# Also good
def test_invalid_api_key_returns_401():
    pass
```

### 4. Arrange-Act-Assert Pattern

```python
def test_cache_set_and_get():
    # Arrange - set up test data
    cache = CacheManager()
    key = "test_key"
    value = "test_value"
    
    # Act - perform the action
    cache.set(key, value)
    result = cache.get(key)
    
    # Assert - verify the outcome
    assert result == value
```

### 5. Keep Tests Independent

```python
# Bad - tests depend on each other
def test_create_user():
    global user
    user = User("john")

def test_user_name():
    assert user.name == "john"  # Depends on previous test!

# Good - independent tests
@pytest.fixture
def user():
    return User("john")

def test_create_user(user):
    assert user is not None

def test_user_name(user):
    assert user.name == "john"
```

### 6. Mock External Dependencies

```python
# Good - mock external API calls
@patch('requests.get')
def test_fetch_data(mock_get):
    mock_get.return_value.json.return_value = {"data": "test"}
    result = fetch_external_data()
    assert result == {"data": "test"}
```

### 7. Test Edge Cases

```python
@pytest.mark.parametrize("input,expected", [
    ("normal", "valid"),      # Normal case
    ("", "empty"),            # Empty input
    (None, "none"),           # None input
    ("x" * 1000, "long"),     # Very long input
    ("特殊字符", "unicode"),   # Unicode
])
def test_edge_cases(input, expected):
    assert process(input) == expected
```

### 8. Clean Up After Tests

```python
@pytest.fixture
async def temp_file():
    """Create temporary file for testing"""
    file_path = "/tmp/test_file.txt"
    
    # Setup
    with open(file_path, 'w') as f:
        f.write("test data")
    
    yield file_path
    
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
```

---

## Troubleshooting

### Issue 1: Tests Fail Locally But Pass in CI

**Cause:** Different environment or dependencies

**Solution:**
```bash
# Use same Python version as CI
pyenv install 3.12
pyenv local 3.12

# Recreate virtual environment
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests with same settings as CI
pytest --strict-markers --strict-config
```

### Issue 2: Slow Tests

**Cause:** Integration tests or external API calls

**Solution:**
```bash
# Run only fast unit tests
pytest -m "unit and not slow"

# Run tests in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

### Issue 3: Redis/PostgreSQL Connection Errors

**Cause:** Services not running

**Solution:**
```bash
# Start services
docker-compose up -d redis postgres

# Check services are running
docker-compose ps

# View service logs
docker-compose logs redis postgres
```

### Issue 4: Import Errors

**Cause:** Python path not configured

**Solution:**
```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use pytest.ini (already configured)
# pythonpath = .
```

### Issue 5: Async Test Warnings

**Cause:** Missing pytest-asyncio or incorrect mode

**Solution:**
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Check pytest.ini has:
# asyncio_mode = auto
```

### Issue 6: Coverage Not Including Files

**Cause:** Files not imported or incorrect source path

**Solution:**
```bash
# Check coverage configuration in pytest.ini
# [coverage:run]
# source = app

# Force coverage of specific modules
pytest --cov=app.core --cov=app.api
```

---

## Writing Your First Test

Let's write a test for a new feature:

### Step 1: Create Test File

```bash
touch tests/unit/test_my_feature.py
```

### Step 2: Write Test

```python
# tests/unit/test_my_feature.py
import pytest
from app.core.my_feature import process_data

@pytest.mark.unit
def test_process_data_with_valid_input():
    """Test that process_data handles valid input correctly"""
    # Arrange
    input_data = {"name": "John", "age": 30}
    
    # Act
    result = process_data(input_data)
    
    # Assert
    assert result["name"] == "John"
    assert result["age"] == 30
    assert result["processed"] is True

@pytest.mark.unit
def test_process_data_with_invalid_input():
    """Test that process_data raises error for invalid input"""
    with pytest.raises(ValueError):
        process_data(None)
```

### Step 3: Run Test

```bash
pytest tests/unit/test_my_feature.py -v
```

### Step 4: Check Coverage

```bash
pytest tests/unit/test_my_feature.py --cov=app.core.my_feature --cov-report=term-missing
```

---

## Additional Resources

- **Pytest Documentation:** https://docs.pytest.org/
- **pytest-asyncio:** https://pytest-asyncio.readthedocs.io/
- **Coverage.py:** https://coverage.readthedocs.io/
- **Testing Best Practices:** https://docs.python-guide.org/writing/tests/
- **FastAPI Testing:** https://fastapi.tiangolo.com/tutorial/testing/

---

## Next Steps

1. ✅ Review existing tests in `tests/` directory
2. ✅ Run test suite and check coverage
3. ✅ Identify modules with low coverage
4. ✅ Write tests for uncovered code
5. ✅ Set up pre-commit hooks to run tests
6. ✅ Configure your IDE for test running

---

**Last Updated:** October 8, 2025  
**Version:** 1.0
