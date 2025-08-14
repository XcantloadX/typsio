# Publishing Scripts Usage

This directory contains scripts for publishing typsio packages:

## Script Files

1. `publish.sh` - Bash script (Linux/macOS)
2. `publish.ps1` - PowerShell script (Windows)

## Usage

### Bash Script (Linux/macOS)

```bash
cd /path/to/typsio/scripts
./publish.sh
```

### PowerShell Script (Windows)

```powershell
cd /path/to/typsio/scripts
./publish.ps1
```

## Prerequisites

1. **Python Package Publishing**:
   - Install `build` and `twine`: `pip install build twine`
   - Configure PyPI credentials: `twine check` or use `.pypirc` file

2. **TypeScript Package Publishing**:
   - Install Node.js and npm
   - Login to npm: `npm login`

## Script Functionality

1. Builds and publishes Python package to PyPI
2. Builds and publishes TypeScript package to npm

## Notes

- Ensure you have updated the version numbers in both packages before publishing
- Python package version is in `packages/py_typsio/pyproject.toml`
- TypeScript package version is in `packages/ts_typsio/package.json`