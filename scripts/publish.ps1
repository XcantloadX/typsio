# PowerShell script to publish typsio packages
# This script builds and publishes both Python and TypeScript packages

Write-Host "Starting typsio package publishing..." -ForegroundColor Green

# Get script directory
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$ProjectRoot = Split-Path $ScriptDir -Parent

Write-Host "Project root directory: $ProjectRoot" -ForegroundColor Cyan

# Navigate to project root
Set-Location $ProjectRoot

# Publish Python package
Write-Host "Publishing Python package..." -ForegroundColor Blue
Set-Location "$ProjectRoot/packages/py_typsio"

# Check version
Write-Host "Checking version..." -ForegroundColor Cyan
$PyProjectContent = Get-Content pyproject.toml
$VersionLine = $PyProjectContent -match '^version = "[0-9]+\.[0-9]+\.[0-9]+"'
$Version = [regex]::Match($VersionLine, 'version = "([0-9]+\.[0-9]+\.[0-9]+)"').Groups[1].Value
Write-Host "Python package version: $Version" -ForegroundColor Cyan

# Build Python package
Write-Host "Building Python package..." -ForegroundColor Yellow
python -m build

# Upload to PyPI (requires twine configuration)
Write-Host "Uploading Python package to PyPI..." -ForegroundColor Yellow
twine upload dist/*

Write-Host "Python package published successfully" -ForegroundColor Green

# Publish TypeScript package
Write-Host "Publishing TypeScript package..." -ForegroundColor Blue
Set-Location "$ProjectRoot/packages/ts_typsio"

# Check version
Write-Host "Checking version..." -ForegroundColor Cyan
$PackageJson = Get-Content package.json | ConvertFrom-Json
$Version = $PackageJson.version
Write-Host "TypeScript package version: $Version" -ForegroundColor Cyan

# Build TypeScript package
Write-Host "Building TypeScript package..." -ForegroundColor Yellow
npm run build

# Publish to npm (requires npm login)
Write-Host "Uploading TypeScript package to npm..." -ForegroundColor Yellow
npm publish

Write-Host "TypeScript package published successfully" -ForegroundColor Green

# Back to project root
Set-Location $ProjectRoot

Write-Host "All packages published successfully!" -ForegroundColor Green