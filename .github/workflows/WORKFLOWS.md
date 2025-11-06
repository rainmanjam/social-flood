# GitHub Actions Workflows Documentation

This document explains when and how the various GitHub Actions workflows are triggered in the Social Flood project.

## Workflows Overview

| Workflow | File | Purpose |
|----------|------|---------|
| CI/CD Pipeline | `main.yml` | Runs tests, linting, builds, and security scans |
| Security Scanning | `security.yml` | Comprehensive security scanning (weekly + on-demand) |
| Docker Build | `docker-build-sign.yml` | Builds Docker images on pull requests |
| Release | `release.yml` | Automated versioning and releases |

---

## CI/CD Pipeline (`main.yml`)

### When Tests Run

The CI/CD pipeline runs tests **automatically** on the following events:

#### 1. **Push to Protected Branches**
Tests run when code is pushed to:
- `main` (production branch)
- `develop` (development branch)
- `feature/*` (feature branches)
- `bugfix/*` (bug fix branches)
- `hotfix/*` (hotfix branches)
- `release/*` (release branches)

```yaml
on:
  push:
    branches: [main, develop, 'feature/**', 'bugfix/**', 'hotfix/**', 'release/**']
```

#### 2. **Pull Requests**
Tests run automatically when pull requests are:
- **Opened** - When a new PR is created
- **Synchronized** - When new commits are pushed to the PR branch
- **Reopened** - When a closed PR is reopened
- **Ready for Review** - When a draft PR is marked as ready

```yaml
on:
  pull_request:
    branches: [main, develop]
    types: [opened, synchronize, reopened, ready_for_review]
```

**Target Branches:** Tests only run for PRs targeting `main` or `develop`.

#### 3. **Merge Queue**
Tests run when using GitHub's merge queue feature:
```yaml
on:
  merge_group:
    branches: [main, develop]
```

#### 4. **Manual Trigger**
You can manually trigger the workflow from the GitHub Actions UI:
- Go to **Actions** → **CI/CD Pipeline** → **Run workflow**
- Option: Choose to run the full test suite (including slow tests)

```yaml
on:
  workflow_dispatch:
    inputs:
      run_full_suite:
        description: 'Run full test suite including slow tests'
        type: boolean
        default: false
```

---

### Test Behavior

#### **Draft Pull Requests**
- Tests are **skipped** on draft PRs to save CI resources
- Tests will run once the PR is marked as "Ready for Review"
- Exception: Manual workflow dispatch will run tests even on drafts

#### **Fast vs. Full Test Suite**

**Fast Tests (Default on feature branches):**
- Excludes tests marked with `@pytest.mark.slow`
- Runs on: feature branches, bugfix branches, etc.
- Command: `pytest -m "not slow" tests/`

**Full Test Suite (On main branch and manual runs):**
- Includes all tests (including slow integration tests)
- Runs on: `main` branch, manual workflow dispatch with `run_full_suite=true`
- Command: `pytest tests/`

#### **Multi-Version Testing**
Tests run against multiple Python versions in parallel:
- Python 3.11
- Python 3.12
- Python 3.13

---

### Job Execution Order

```
┌─────────────────────────────────────────────────┐
│ 1. Lint & Format Check (runs first)            │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 2. Tests (3.11, 3.12, 3.13 in parallel)        │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 3. Docker Build (only on main/develop/PRs)     │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 4. Security Scan (runs in parallel)            │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ 5. CI/CD Summary (always runs, shows results)  │
└─────────────────────────────────────────────────┘
```

---

### Docker Build Conditions

Docker images are **only built** when:
1. Pushing to `main` branch
2. Pushing to `develop` branch
3. Pull requests targeting `main` or `develop`
4. Merge queue operations

**Not built on:** Feature branches (to save CI time and resources)

---

## Security Scanning (`security.yml`)

### When Security Scans Run

1. **Push to main or develop branches**
2. **Pull requests to main**
3. **Scheduled weekly** (Mondays at 9 AM UTC)
4. **Manual trigger** via workflow dispatch

### Security Tools

- **CodeQL** - Static analysis for security vulnerabilities
- **Trivy** - Container and filesystem vulnerability scanning
- **Gitleaks** - Secret detection in git history
- **Bandit** - Python security linting
- **OWASP Dependency Check** - Dependency vulnerability scanning
- **Dependency Review** - GitHub's dependency review (PRs only)

---

## Docker Build (`docker-build-sign.yml`)

Runs on **pull requests to main** only. This is a lightweight build check to ensure Docker images can be built successfully before merging.

---

## Release Workflow (`release.yml`)

### Automatic Version Bumping
Runs on **push to main** when pushed by a human (not github-actions bot):
1. Increments patch version in `app/__version__.py`
2. Commits and pushes version bump
3. Triggers release creation

### Release Creation
Runs on **push to main** when pushed by github-actions bot:
1. Builds multi-arch Docker images (amd64, arm64)
2. Pushes to Docker Hub and GitHub Container Registry
3. Signs images with Cosign
4. Creates SBOM (Software Bill of Materials)
5. Creates GitHub release with notes

---

## Common Scenarios

### Scenario 1: Working on a Feature Branch
```bash
# You're working on: feature/add-new-api

# Push commits
git push origin feature/add-new-api
# ✅ Tests run (fast tests, no slow tests)
# ❌ Docker image NOT built (saves time)
```

### Scenario 2: Creating a Pull Request
```bash
# Create PR: feature/add-new-api → main

# PR created
# ✅ Tests run on all 3 Python versions
# ✅ Linting checks run
# ✅ Docker image built and tested
# ✅ Security scan runs
```

### Scenario 3: Draft PR → Ready for Review
```bash
# Mark draft PR as "Ready for Review"
# ✅ Tests run immediately
# ✅ All CI checks execute
```

### Scenario 4: Merging to Main
```bash
# Merge PR to main

# After merge:
# ✅ Full test suite runs (including slow tests)
# ✅ Docker image built
# ✅ Version bumped automatically
# ✅ Release created
# ✅ Docker images published
```

### Scenario 5: Running Manual Tests with Slow Tests
```bash
# Go to: Actions → CI/CD Pipeline → Run workflow
# Select branch: develop
# Check: "Run full test suite including slow tests"
# Click: "Run workflow"

# ✅ Full test suite runs on selected branch
```

---

## Best Practices

### For Developers

1. **Use Draft PRs** for work-in-progress to avoid wasting CI resources
2. **Run local tests** before pushing (use `pytest -m "not slow"` for quick feedback)
3. **Use conventional commits** for clear history
4. **Keep PRs small** for faster CI execution and easier review

### For Code Review

1. **Check CI status** before reviewing (all checks should pass)
2. **Review test coverage** in the Codecov report
3. **Check security scan results** in the Security tab
4. **Verify Docker build** succeeded

### For CI/CD Optimization

1. **Fast tests on branches** - Only slow tests on main
2. **Skip Docker builds** on feature branches
3. **Parallel test execution** across Python versions
4. **Caching dependencies** for faster builds
5. **Fail-fast disabled** - All Python versions tested even if one fails

---

## Troubleshooting

### Tests Not Running?

**Check:**
1. Is the PR a draft? → Mark as "Ready for Review"
2. Is the branch name correct? → Must match patterns (feature/*, etc.)
3. Is the target branch main or develop? → Other branches won't trigger tests

### Docker Build Failing?

**Check:**
1. Is the Dockerfile valid? → Test locally with `docker build .`
2. Are all dependencies in requirements.txt? → Verify locally
3. Base image accessible? → Check if `python:3.13-slim-bookworm` is available

### Tests Timing Out?

**Check:**
1. Are slow tests running on a feature branch? → They should be skipped
2. Is there an infinite loop in the code? → Review recent changes
3. External API dependencies? → Mock them in tests

---

## Environment Variables

The CI/CD workflows use these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHON_VERSION` | Default Python version for CI | `3.13` |
| `ENABLE_API_KEY_AUTH` | Enable API key auth in tests | `false` |

---

## Coverage Reports

Test coverage is automatically uploaded to Codecov for Python 3.13 runs.

- **Location:** Codecov dashboard (linked in PR)
- **Format:** XML, HTML, and terminal output
- **Threshold:** No enforced threshold (informational only)

---

## Getting Help

- **CI/CD Issues:** Check workflow logs in the Actions tab
- **Test Failures:** Review the test output in the job logs
- **Security Alerts:** Check the Security tab on GitHub
- **Questions:** Open a discussion or contact the maintainers

---

## Related Documentation

- [Contributing Guide](../../CONTRIBUTING.md)
- [Security Policy](../../SECURITY_GUIDELINES.md)
- [API Documentation](../../API_REFERENCE.md)
- [Deployment Guide](../../DEPLOYMENT.md)

---

**Last Updated:** 2025-11-06
**Version:** 1.6.0
