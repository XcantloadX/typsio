#!/bin/bash

# Script to publish typsio packages
# This script builds and publishes both Python and TypeScript packages

set -e  # Exit on error

echo "Starting typsio package publishing..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Project root directory: $PROJECT_ROOT"

# Navigate to project root
cd "$PROJECT_ROOT"

# Publish Python package
echo "Publishing Python package..."
cd "$PROJECT_ROOT/packages/py_typsio"

# Copy README.md to the Python package directory
echo "Copying README.md to the Python package directory..."
cp "$PROJECT_ROOT/README.md" .

# Check version
echo "Checking version..."
VERSION=$(grep -E '^version = "[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml | sed -E 's/version = "([0-9]+\.[0-9]+\.[0-9]+)"/\1/')
echo "Python package version: $VERSION"

# Build Python package
echo "Building Python package..."
python3 -m build

# Upload to PyPI (requires twine configuration)
echo "Uploading Python package to PyPI..."
twine upload dist/*

echo "Python package published successfully"

# Publish TypeScript package
echo "Publishing TypeScript package..."
cd "$PROJECT_ROOT/packages/ts_typsio"

# Check version
echo "Checking version..."
VERSION=$(grep -E '"version": "[0-9]+\.[0-9]+\.[0-9]+"' package.json | sed -E 's/.*"version": "([0-9]+\.[0-9]+\.[0-9]+)".*/\1/')
echo "TypeScript package version: $VERSION"

# Build TypeScript package
echo "Building TypeScript package..."
npm run build

# Publish to npm (requires npm login)
echo "Uploading TypeScript package to npm..."
npm publish

echo "TypeScript package published successfully"

# Back to project root
cd "$PROJECT_ROOT"

echo "All packages published successfully!"