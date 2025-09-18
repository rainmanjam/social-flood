#!/bin/bash

# Code Quality Check Script
# This script runs comprehensive code quality checks on the Social Flood API

set -e

echo "🔍 Running Code Quality Checks for Social Flood API"
echo "=================================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
echo "📋 Checking required tools..."
missing_tools=()

if ! command_exists black; then
    missing_tools+=("black")
fi

if ! command_exists isort; then
    missing_tools+=("isort")
fi

if ! command_exists pylint; then
    missing_tools+=("pylint")
fi

if ! command_exists pytest; then
    missing_tools+=("pytest")
fi

if [ ${#missing_tools[@]} -ne 0 ]; then
    echo "❌ Missing required tools: ${missing_tools[*]}"
    echo "Run: pip install ${missing_tools[*]}"
    exit 1
fi

echo "✅ All required tools are available"

# Set up environment
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo ""
echo "🎨 Running code formatters..."
echo "================================"

# Format with black
echo "Running Black formatter..."
black --line-length 120 app/ --check --diff

# Sort imports
echo "Running isort..."
isort --line-length 120 --check-only --diff app/

echo ""
echo "🔍 Running linters..."
echo "===================="

# Run pylint on core modules first
echo "Running pylint on core modules..."
pylint app/core/ --max-line-length=120 --score=yes || true

# Run pylint on API modules
echo "Running pylint on API modules..."
pylint app/api/ --max-line-length=120 --score=yes || true

echo ""
echo "🧪 Running tests..."
echo "=================="

# Run tests with coverage
pytest --cov=app --cov-report=term-missing --cov-report=html tests/ -v

echo ""
echo "📊 Test Coverage Report"
echo "======================"
echo "HTML coverage report generated in: htmlcov/index.html"

echo ""
echo "🎯 Code Quality Summary"
echo "======================"

# Count lines of code
echo "📈 Code Statistics:"
find app/ -name "*.py" -exec wc -l {} + | tail -1

# Count TODO/FIXME comments
todo_count=$(grep -r "TODO\|FIXME\|XXX\|HACK" app/ --include="*.py" | wc -l)
echo "📝 TODO/FIXME comments: $todo_count"

# Count functions and classes
func_count=$(grep -r "def " app/ --include="*.py" | wc -l)
class_count=$(grep -r "class " app/ --include="*.py" | wc -l)
async_count=$(grep -r "async def" app/ --include="*.py" | wc -l)

echo "🏗️  Architecture:"
echo "   - Functions: $func_count (async: $async_count)"
echo "   - Classes: $class_count"

echo ""
echo "✅ Code quality check complete!"
echo "================================"

# Exit with success if we got here
exit 0