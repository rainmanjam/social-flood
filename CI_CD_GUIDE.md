# CI/CD Pipeline Guide

Complete guide to the Continuous Integration and Continuous Deployment pipeline for Social Flood API.

---

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Getting Started](#getting-started)
4. [Workflows](#workflows)
5. [Docker Hub Integration](#docker-hub-integration)
6. [GitHub Releases](#github-releases)
7. [Versioning Strategy](#versioning-strategy)
8. [Security Features](#security-features)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

Our CI/CD pipeline automates:
- ✅ Code quality checks (linting, formatting, type checking)
- ✅ Automated testing (unit, integration, security)
- ✅ Docker image building (multi-architecture)
- ✅ Image signing and attestation (cosign, SBOM)
- ✅ Deployment to Docker Hub and GitHub Container Registry
- ✅ Automated versioning and GitHub releases

### Pipeline Triggers

| Event | Workflow | Description |
|-------|----------|-------------|
| Push to `main` | Full CI/CD | Tests + Deploy + Release |
| Push to `develop` | CI Only | Tests + Build (no deploy) |
| Push to `feature/**` | CI Only | Tests + Build (no deploy) |
| Pull Request | CI + Build Check | Tests + Docker build validation |
| Manual | Any workflow | Trigger via GitHub Actions UI |

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Push to Branch                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Code Quality Checks        │
        │  • Black, isort, Flake8      │
        │  • Pylint, MyPy              │
        │  • Bandit (security)         │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │      Test Suite              │
        │  • Unit tests (3.10-3.12)    │
        │  • Integration tests         │
        │  • Coverage reporting        │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Security Scanning          │
        │  • Dependency check (Safety) │
        │  • Security scan (Bandit)    │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Build Docker Image         │
        │  • Multi-arch (amd64, arm64) │
        │  • Caching enabled           │
        └──────────┬───────────────────┘
                   │
                   ▼ (only on main branch)
        ┌──────────────────────────────┐
        │   Deploy to Registries       │
        │  • Docker Hub                │
        │  • GitHub Container Registry │
        │  • Sign with cosign          │
        │  • Generate SBOM             │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Create GitHub Release      │
        │  • Version tag               │
        │  • Auto-generated changelog  │
        │  • Release notes             │
        └──────────────────────────────┘
```

---

## Getting Started

### Prerequisites

1. **GitHub Account** with admin access to repository
2. **Docker Hub Account** for image hosting
3. **Git** installed locally
4. **Python 3.10+** installed

### Initial Setup

#### 1. Configure GitHub Secrets

Go to: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username | e.g., `johndoe` |
| `DOCKERHUB_TOKEN` | Docker Hub access token | Created at hub.docker.com/settings/security |

**How to create Docker Hub token:**

1. Go to <https://hub.docker.com/settings/security>
2. Click "New Access Token"
3. Name: `GitHub Actions`
4. Permissions: `Read, Write, Delete`
5. Copy token (save it - won't show again!)
6. Add to GitHub secrets

#### 2. Enable GitHub Actions

```bash
# Actions should be enabled by default
# If not, go to: Settings → Actions → General → Allow all actions
```

#### 3. Configure Branch Protection (Optional but Recommended)

Go to: `Settings` → `Branches` → `Add rule`

**For `main` branch:**
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
  - Select: `Code Quality Checks`, `Test Suite`, `Build Docker Image`
- ✅ Require branches to be up to date before merging
- ✅ Include administrators

---

## Workflows

We have 4 main workflows:

### 1. Comprehensive CI/CD Pipeline (`ci-cd.yml`)

**Triggers:**
- Push to `main`, `develop`, `feature/**`
- Pull requests to `main`, `develop`

**Jobs:**

#### Job 1: Code Quality (runs on all branches)
```yaml
Steps:
1. Checkout code
2. Setup Python 3.12
3. Install linting tools
4. Run Black (formatter check)
5. Run isort (import sorting)
6. Run Flake8 (style guide)
7. Run Pylint (code analysis)
8. Run MyPy (type checking)
9. Run Bandit (security linting)
10. Upload security report
```

#### Job 2: Test Suite (runs on all branches)
```yaml
Matrix: Python 3.10, 3.11, 3.12
Services: Redis, PostgreSQL

Steps:
1. Checkout code
2. Setup Python (matrix version)
3. Install dependencies
4. Setup test environment
5. Run unit tests with coverage
6. Run integration tests
7. Upload coverage to Codecov
8. Upload test results
```

#### Job 3: Security Scan (runs on all branches)
```yaml
Steps:
1. Checkout code
2. Setup Python
3. Install security tools
4. Run Safety (dependency check)
5. Run Bandit (security scan)
6. Upload reports
```

#### Job 4: Build Docker (runs on all branches)
```yaml
Steps:
1. Checkout code
2. Setup Docker Buildx
3. Build multi-arch image
4. Upload image artifact
```

#### Job 5: Deploy (main branch only)
```yaml
Steps:
1. Checkout code
2. Get current version
3. Check if tag exists
4. Login to Docker Hub
5. Login to GitHub Container Registry
6. Build and push images
7. Sign images with cosign
8. Create version tag
9. Generate changelog
10. Create GitHub release
```

### 2. Release Workflow (`release.yml`)

**Purpose:** Legacy release workflow with automatic version bumping

**Triggers:** Push to `main`

**Jobs:**
1. **bump-version:** Increment version in `app/__version__.py`
2. **release:** Build, sign, and publish Docker images + GitHub release

**Note:** This workflow is being replaced by `ci-cd.yml` for better integration.

### 3. Docker Build (`docker-build-sign.yml`)

**Purpose:** Build-only workflow for pull requests

**Triggers:** Pull requests to `main`

**What it does:**
- Validates that Docker image builds successfully
- Tests multi-architecture support
- Does NOT push to registry

### 4. Update Base Image (`update-base-image.yml`)

**Purpose:** Automated base image updates

**Triggers:** 
- Weekly schedule (Mondays 00:00 UTC)
- Manual trigger

**What it does:**
- Rebuilds with latest base image
- Security patches
- Dependency updates

---

## Docker Hub Integration

### Multi-Architecture Support

We build for two architectures:
- **linux/amd64** (Intel/AMD - most common)
- **linux/arm64** (ARM - Apple Silicon, AWS Graviton, etc.)

### Image Tags

Every deployment creates multiple tags:

| Tag Pattern | Example | Description |
|-------------|---------|-------------|
| `latest` | `latest` | Always points to newest release |
| Version | `1.0.0` | Specific version number |
| Branch + SHA | `main-a1b2c3d` | Branch name + commit hash |

### Image Naming

```bash
# Docker Hub
<username>/social-flood:<tag>
# Example: johndoe/social-flood:1.0.0

# GitHub Container Registry
ghcr.io/<owner>/<repo>:<tag>
# Example: ghcr.io/rainmanjam/social-flood:1.0.0
```

### Pulling Images

```bash
# Latest version
docker pull <username>/social-flood:latest

# Specific version
docker pull <username>/social-flood:1.0.0

# From GitHub Container Registry
docker pull ghcr.io/rainmanjam/social-flood:latest
```

### Image Security

Every image includes:
1. **Cryptographic Signature** (cosign)
2. **SBOM** (Software Bill of Materials)
3. **Provenance Attestation**

Verify signatures:

```bash
# Install cosign
brew install cosign  # macOS
# or download from: https://github.com/sigstore/cosign/releases

# Verify image
cosign verify <username>/social-flood:1.0.0
```

---

## GitHub Releases

### Automatic Release Creation

When code is pushed to `main`:

1. **Version Detection:**
   - Reads version from `app/__version__.py`
   - Checks if release for that version already exists

2. **Docker Build:**
   - Builds multi-arch images
   - Pushes to Docker Hub + GHCR
   - Signs with cosign
   - Creates SBOM

3. **GitHub Release:**
   - Creates release with version tag (e.g., `v1.0.0`)
   - Generates changelog from commits
   - Includes deployment instructions
   - Adds verification commands

### Release Notes Structure

```markdown
## 🚀 Release v1.0.0

### 📋 What's Changed
- feat: Add Reddit API integration (abc123)
- fix: Resolve cache timeout issue (def456)
- chore: Update dependencies (ghi789)

### 🐳 Docker Images
**Docker Hub:**
docker pull johndoe/social-flood:1.0.0

**GitHub Container Registry:**
docker pull ghcr.io/rainmanjam/social-flood:1.0.0

### 🔒 Security
- ✅ All images cryptographically signed
- ✅ Security scans passed
- ✅ Dependencies checked

### 🔍 Verify Signatures
cosign verify johndoe/social-flood:1.0.0
```

### Viewing Releases

1. Go to repository main page
2. Click "Releases" (right sidebar)
3. View all releases with tags

### Downloading Release Artifacts

While we don't attach files to releases, you can:

1. Pull Docker images (see tags in release notes)
2. Clone specific version: `git clone -b v1.0.0 <repo-url>`
3. Download workflow artifacts from Actions tab

---

## Versioning Strategy

### Current Approach: Manual Versioning

**Location:** `app/__version__.py`

```python
__version__ = "1.0.0"
```

**Process:**
1. Update version in `app/__version__.py`
2. Commit with message: `chore: bump version to 1.0.0`
3. Push to `main`
4. CI/CD automatically creates release

### Version Format: Semantic Versioning

We follow [SemVer](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR** (1.x.x): Breaking changes, incompatible API changes
- **MINOR** (x.1.x): New features, backwards-compatible
- **PATCH** (x.x.1): Bug fixes, backwards-compatible

### When to Bump Which Number

| Change Type | Version Part | Example |
|-------------|--------------|---------|
| Breaking API change | MAJOR | 1.0.0 → 2.0.0 |
| New feature | MINOR | 1.0.0 → 1.1.0 |
| Bug fix | PATCH | 1.0.0 → 1.0.1 |
| Security patch | PATCH | 1.0.0 → 1.0.1 |
| Dependency update | PATCH | 1.0.0 → 1.0.1 |

### Conventional Commits (Optional Enhancement)

For better automation, you can use conventional commit messages:

```bash
# New feature (minor version bump)
git commit -m "feat: add Reddit API integration"

# Bug fix (patch version bump)
git commit -m "fix: resolve cache timeout issue"

# Breaking change (major version bump)
git commit -m "feat!: change API response format

BREAKING CHANGE: API now returns JSON instead of XML"

# Other types (no version bump)
git commit -m "docs: update README"
git commit -m "chore: update dependencies"
git commit -m "test: add unit tests for auth"
```

### Future: Automated Semantic Versioning

To enable automatic version bumping based on commits:

1. Install semantic-release:
```bash
npm install -g semantic-release
```

2. Update workflow to use semantic-release
3. Commit messages determine version bumps automatically

---

## Security Features

### 1. Code Security Scanning

**Bandit:** Scans Python code for security issues

```yaml
- name: Run Bandit
  run: bandit -r app/ -f json -o bandit-report.json
```

Checks for:
- SQL injection vulnerabilities
- Hardcoded passwords
- Use of unsafe functions
- Insecure random number generation

### 2. Dependency Vulnerability Scanning

**Safety:** Checks dependencies against CVE database

```yaml
- name: Run Safety Check
  run: safety check --json --output safety-report.json
```

Flags:
- Known vulnerabilities in packages
- Outdated dependencies with security fixes
- License issues

### 3. Container Image Signing

**Cosign:** Cryptographically signs Docker images

```yaml
- name: Sign Docker images
  run: |
    cosign sign --yes ${{ env.REGISTRY_IMAGE }}:${{ version }}
```

Benefits:
- Verify image authenticity
- Detect tampering
- Supply chain security

### 4. Software Bill of Materials (SBOM)

**Syft:** Generates SBOM for images

```yaml
- name: Create SBOM attestation
  run: |
    syft <image> -o spdx-json > sbom.json
    cosign attest --predicate sbom.json <image>
```

Provides:
- Complete list of dependencies
- License information
- Vulnerability scanning input

### 5. Secrets Management

**Best Practices:**
- ✅ Use GitHub Secrets for sensitive data
- ✅ Never commit credentials to code
- ✅ Rotate secrets regularly
- ✅ Use least-privilege access tokens

---

## Troubleshooting

### Issue 1: Workflow Fails with "Secret not found"

**Error:**
```
Error: Secret DOCKERHUB_USERNAME not found
```

**Solution:**
1. Go to `Settings` → `Secrets and variables` → `Actions`
2. Add missing secret
3. Re-run workflow

### Issue 2: Docker Build Fails

**Error:**
```
ERROR: failed to solve: process "/bin/sh -c pip install ..." did not complete successfully
```

**Solution:**
```bash
# Test Docker build locally
docker build -t test-build .

# Check for issues in Dockerfile
# Common causes:
# - Missing dependencies in requirements.txt
# - Incorrect base image
# - Network issues during build
```

### Issue 3: Tests Fail in CI but Pass Locally

**Common Causes:**
1. Different Python versions
2. Missing environment variables
3. External services not available

**Solution:**
```bash
# Match CI environment locally
python --version  # Should be 3.10, 3.11, or 3.12

# Start required services
docker-compose up -d redis postgres

# Run tests with same config as CI
pytest --strict-markers --strict-config
```

### Issue 4: Coverage Below Threshold

**Error:**
```
Coverage: 65% (minimum required: 70%)
```

**Solution:**
```bash
# Check coverage locally
pytest --cov=app --cov-report=term-missing

# Identify uncovered lines
# Write tests for missing coverage
# Or adjust threshold in pytest.ini
```

### Issue 5: Image Signing Fails

**Error:**
```
Error: signing <image>: getting remote image: GET https://...
```

**Solution:**
1. Check cosign is installed in workflow
2. Verify image was pushed successfully
3. Check permissions for GITHUB_TOKEN

### Issue 6: Version Tag Already Exists

**Error:**
```
Release v1.0.0 already exists
```

**Solution:**
```bash
# Update version in app/__version__.py
# Change from 1.0.0 to 1.0.1 (or appropriate bump)

# Then commit and push
git add app/__version__.py
git commit -m "chore: bump version to 1.0.1"
git push origin main
```

---

## Best Practices

### 1. Keep Main Branch Stable

- ✅ Always work in feature branches
- ✅ Create pull requests for review
- ✅ Merge only after CI passes
- ✅ Never force push to main

### 2. Write Good Commit Messages

```bash
# Good
git commit -m "feat: add rate limiting to API endpoints"
git commit -m "fix: resolve authentication token expiry issue"
git commit -m "docs: update API documentation for v2.0"

# Bad
git commit -m "fixed stuff"
git commit -m "updates"
git commit -m "wip"
```

### 3. Use Feature Branches

```bash
# Create feature branch
git checkout -b feature/add-redis-caching

# Work on feature
# ...

# Push to remote
git push origin feature/add-redis-caching

# Create PR on GitHub
# Merge after review and CI pass
```

### 4. Test Before Pushing

```bash
# Run tests locally
pytest

# Check code quality
black --check app/ tests/
flake8 app/ tests/

# Build Docker image
docker build -t test-build .
```

### 5. Review CI Logs

- Always check failed workflow logs
- Download artifacts for detailed reports
- Fix issues before requesting review

### 6. Keep Dependencies Updated

```bash
# Check for outdated packages
pip list --outdated

# Update requirements.txt
pip install --upgrade package-name
pip freeze > requirements.txt

# Test after updates
pytest
```

### 7. Monitor Docker Hub Usage

- Check image pull statistics
- Monitor storage usage
- Delete old unused tags
- Use image retention policies

### 8. Version Bumping Guidelines

- Bump version BEFORE merging to main
- Follow SemVer strictly
- Document breaking changes in CHANGELOG
- Tag releases consistently

---

## Workflow Customization

### Adding a New Job

Edit `.github/workflows/ci-cd.yml`:

```yaml
jobs:
  # ... existing jobs ...
  
  my-new-job:
    name: My Custom Job
    runs-on: ubuntu-latest
    needs: [test]  # Run after test job
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Custom step
        run: |
          echo "Running custom job"
          # Your commands here
```

### Adding Environment Variables

```yaml
env:
  MY_CUSTOM_VAR: "value"
  PYTHON_VERSION: '3.12'
```

### Running Jobs Conditionally

```yaml
jobs:
  deploy:
    if: github.ref == 'refs/heads/main'  # Only on main
    # ...
```

### Matrix Testing

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
    os: [ubuntu-latest, macos-latest]
```

---

## Monitoring and Metrics

### GitHub Actions Metrics

View in: `Actions` → `Summary`

- ✅ Workflow run history
- ✅ Success/failure rates
- ✅ Average run duration
- ✅ Billable minutes used

### Docker Hub Metrics

View in: Docker Hub → Repository → `Insights`

- ✅ Pull statistics
- ✅ Storage usage
- ✅ Popular tags
- ✅ Geographic distribution

### Codecov Integration

View coverage trends at: `codecov.io/gh/<owner>/<repo>`

- ✅ Coverage over time
- ✅ File-level coverage
- ✅ PR coverage impact
- ✅ Coverage badges

---

## Next Steps

1. ✅ Set up GitHub secrets (Docker Hub credentials)
2. ✅ Enable branch protection for `main`
3. ✅ Create your first feature branch
4. ✅ Make changes and create PR
5. ✅ Watch CI run automatically
6. ✅ Merge to main and see release created
7. ✅ Pull your Docker image from Docker Hub
8. ✅ Verify image signature with cosign

---

## Additional Resources

- **GitHub Actions Documentation:** <https://docs.github.com/en/actions>
- **Docker Hub:** <https://hub.docker.com/>
- **Semantic Versioning:** <https://semver.org/>
- **Conventional Commits:** <https://www.conventionalcommits.org/>
- **Cosign Documentation:** <https://docs.sigstore.dev/cosign/overview/>

---

**Last Updated:** October 8, 2025  
**Version:** 1.0
