# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed
- Port scanning now skips dependency, cache and VCS directories (`node_modules`, `.venv`, `.git`, `__pycache__`, and similar) when collecting used ports, so ports are no longer reserved from `.env` files that sprout did not generate. A directory whose name is on that list is still walked when it is a worktree root, so a branch named `venv` keeps its own ports reserved
- `find_available_port()` accepts an optional set of already-used ports, letting callers scan the workspace once instead of once per allocated port
- `parse_env_template()` treats its `used_ports` argument as a replacement for the workspace scan rather than an addition to it, and scans the workspace only when the template actually contains `{{ auto_port() }}`

### Deprecated

### Removed

### Fixed
- `sprout create` no longer rescans every worktree for each `{{ auto_port() }}` placeholder, and the scan it does run no longer descends into dependency directories. Together, on a workspace with 8 auto-assigned ports and ~490k files under `.sprout/`, the `.env` generation step dropped from 97s to 2s

### Security

## [0.8.0] - 2026-06-08

### Added

### Changed
- Migrated the package's PyPI publishing account and GitHub organization references from SecDev-Lab to AgenticSec (package author and project URLs now point to AgenticSec)

### Deprecated

### Removed

### Fixed

### Security

## [0.7.0] - 2025-10-28

### Added
- Support for default values in `.env.example` templates using `{{ VARIABLE | default_value }}` syntax
  - Works with environment variables: `{{ API_KEY | dev-key }}` - uses default when variable is not set
  - Works with function placeholders: `{{ branch() | main }}` - uses default when branch name is not provided
  - Supports empty string as default: `{{ VAR | }}` - uses empty string when variable is not set
  - Whitespace around default values is automatically trimmed
  - Environment variables always override default values when set

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.6.0] - 2025-08-17

### Added
- Support for `{{ branch() }}` placeholder in `.env.example` templates - replaced with the current branch/subtree name

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.5.0] - 2025-07-15

### Added
- Support for repositories without `.env.example` files - `sprout create` now works in any git repository

### Changed
- `sprout create` behavior when no `.env.example` files exist: shows warning instead of error and continues creating worktree

### Deprecated

### Removed

### Fixed

### Security

## [0.4.0] - 2025-06-28

### Added
- Support for multiple `.env.example` files throughout the repository, enabling monorepo workflows
- Recursive scanning of `.env` files for port allocation to ensure global uniqueness across all services
- Support for repositories without `.env.example` files - `sprout create` now works in any git repository

### Changed
- Port allocation now ensures uniqueness across all services in all worktrees, preventing Docker host port conflicts
- `sprout create` now processes all `.env.example` files found in the repository while maintaining directory structure
- Only git-tracked `.env.example` files are now processed, preventing unwanted processing of files in `.sprout/` worktrees
- `sprout create` behavior when no `.env.example` files exist: shows warning instead of error and continues creating worktree

### Deprecated

### Removed

### Fixed

### Security

## [0.3.0] - 2025-06-27

### Added
- `--path` flag for `sprout create` command to output only the worktree path, enabling one-liner usage like `cd $(sprout create feature --path)`

### Changed
- Enhanced `sprout path` and `sprout rm` commands to accept index numbers from `sprout ls` output, enabling faster navigation without typing full branch names (e.g., `cd $(sprout path 2)` instead of `cd $(sprout path feature-long-branch-name)`)

### Deprecated

### Removed

### Fixed

### Security

## [0.2.0] - 2025-06-27

### Added
- Initial implementation of sprout CLI tool
- `create` command to create new git worktrees with Docker Compose support
- `ls` command to list all sprout worktrees
- `rm` command to remove sprout worktrees
- `path` command to get the path of a sprout worktree
- Rich terminal output with progress indicators
- Comprehensive test suite with pytest
- Type checking with mypy
- Linting and formatting with ruff
- CI/CD pipeline with GitHub Actions
- Support for Python 3.11, 3.12, and 3.13

[Unreleased]: https://github.com/AgenticSec/sprout/compare/v0.8.0...HEAD
[0.2.0]: https://github.com/AgenticSec/sprout/compare/v0.2.0...HEAD

[0.3.0]: https://github.com/AgenticSec/sprout/compare/v0.3.0...HEAD

[0.4.0]: https://github.com/AgenticSec/sprout/compare/v0.4.0...HEAD

[0.5.0]: https://github.com/AgenticSec/sprout/compare/v0.5.0...HEAD

[0.6.0]: https://github.com/AgenticSec/sprout/compare/v0.6.0...HEAD

[0.7.0]: https://github.com/AgenticSec/sprout/compare/v0.7.0...HEAD

[0.8.0]: https://github.com/AgenticSec/sprout/compare/v0.8.0...HEAD
