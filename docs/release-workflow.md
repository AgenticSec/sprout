# Release Workflow Documentation

This document describes the release process for the sprout-cli package.

## Overview

The release process is fully automated through GitHub Actions and can be triggered entirely from the GitHub Web UI. No CLI commands are required.

## Prerequisites

1. **Repository Secrets**: The following secrets must be configured in GitHub repository settings:
   - `PYPI_API_TOKEN`: PyPI authentication token for production releases
   - `TEST_PYPI_API_TOKEN`: Test PyPI token (optional, for testing releases)

2. **Changelog**: All changes must be documented in `CHANGELOG.md` using the Keep a Changelog format.

## Release Process

### 1. Update CHANGELOG

Before releasing, ensure all changes are documented in the `[Unreleased]` section of `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added
- New feature descriptions

### Fixed
- Bug fix descriptions
```

### 2. Trigger Release

1. Go to the [Actions tab](https://github.com/AgenticSec/sprout/actions) in your GitHub repository
2. Click on "Release" workflow in the left sidebar
3. Click "Run workflow" button
4. Configure the release options:
   - **Mark as pre-release**: Check if this is a beta/alpha release
   - **Upload to Test PyPI first**: Check to test the release on Test PyPI before production
   - **Additional release notes**: Optional extra notes for the GitHub release

5. Click "Run workflow" to start the release

### 3. Automatic Version Detection

The workflow automatically determines the version bump based on your changelog entries:

- **Major version** (1.0.0 → 2.0.0): When `### Removed` section has entries
- **Minor version** (1.0.0 → 1.1.0): When `### Added`, `### Changed`, or `### Deprecated` sections have entries
- **Patch version** (1.0.0 → 1.0.1): When only `### Fixed` or `### Security` sections have entries

### 4. Release Steps

The workflow performs these steps automatically:

1. **Validation**: Checks that CHANGELOG has unreleased entries
2. **Version Detection**: Determines version bump type from changelog
3. **Quality Checks**: Runs all tests, linting, and type checking
4. **Version Updates**: Updates version in `pyproject.toml`, `__init__.py`, and CHANGELOG
5. **Build**: Creates wheel and source distributions
6. **Publish**: Uploads to PyPI (or Test PyPI if selected)
7. **Git Operations**: Creates git tag and pushes changes
8. **GitHub Release**: Creates release with changelog content and artifacts

## Changelog Guidelines

### PR Requirements

All PRs with code changes must update CHANGELOG.md unless they are:
- Documentation-only changes (PRs starting with `docs:`)
- CI/CD changes (PRs starting with `ci:`)
- Chore tasks (PRs starting with `chore:`)
- PRs with `skip-changelog` label

### Changelog Format

Use the Keep a Changelog format:

```markdown
## [Unreleased]

### Added
- New endpoints, features, or functionality

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Vulnerability fixes
```

## Troubleshooting

### Release Fails at Validation
- Ensure CHANGELOG.md has entries in the `[Unreleased]` section
- Check that entries follow the correct format

### PyPI Upload Fails
- Verify `PYPI_API_TOKEN` secret is correctly set
- Check that the package name is available on PyPI
- Try using Test PyPI first to debug issues

### Version Already Exists
- The version might have been manually released
- Check PyPI and git tags to verify
- Update CHANGELOG with a new version if needed