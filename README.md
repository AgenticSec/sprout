# sprout

A CLI tool to automate git worktree and Docker Compose development workflows.

## Features

- 🌱 Create isolated development environments using git worktrees
- 🔧 Automatic `.env` file generation from templates
- 🚢 Smart port allocation to avoid conflicts
- 📁 Centralized worktree management in `.sprout/` directory
- 🎨 Beautiful CLI interface with colors and tables

## Installation

```bash
pip install sprout-cli
```

For development:
```bash
# Clone the repository
git clone https://github.com/AgenticSec/sprout.git
cd sprout

# Install in development mode
pip install -e ".[dev]"
```

## Quick Start

**Note**: Sprout works in any git repository. `.env.example` files are optional - if you don't have them, sprout will simply create worktrees without `.env` generation.

1. (Optional) Create a `.env.example` template in your project root (and optionally in subdirectories) for automatic `.env` generation:
```env
# API Configuration
API_KEY={{ API_KEY }}
API_PORT={{ auto_port() }}

# Database Configuration  
DB_HOST=localhost
DB_PORT={{ auto_port() }}

# Branch-specific Configuration
SERVICE_NAME=myapp-{{ branch() }}
DEPLOYMENT_ENV={{ branch() }}

# Example: Docker Compose variables (preserved as-is)
# sprout will NOT process ${...} syntax - it's passed through unchanged
# DB_NAME=${DB_NAME}
```

For monorepo or multi-service projects, you can create `.env.example` files in subdirectories:
```
repo/
  .env.example          # Root configuration
  service-a/
    .env.example        # Service A specific config
  service-b/
    .env.example        # Service B specific config
```

2. Create and navigate to a new development environment in one command:
```bash
cd $(sprout create feature-branch --path)
```

**What happens when you run `sprout create`:**
- If `.env.example` files exist: Sprout will generate corresponding `.env` files with populated variables and unique port assignments
- If no `.env.example` files exist: Sprout will show a warning and create the worktree without `.env` generation

This single command:
- Creates a new git worktree for `feature-branch`
- Generates `.env` files from your templates (if `.env.example` files exist)
- Outputs the path to the new environment
- Changes to that directory when wrapped in `cd $(...)`

3. Start your services:
```bash
docker compose up -d
```

### Alternative: Two-Step Process

If you prefer to see the creation output first:
```bash
# Create the environment
sprout create feature-branch

# Then navigate to it
cd $(sprout path feature-branch)
```

## Commands

### `sprout create <branch-name> [--path]`
Create a new development environment with automated setup.

Options:
- `--path`: Output only the worktree path (useful for shell command substitution)

Examples:
```bash
# Create and see progress messages
sprout create feature-xyz

# Create and navigate in one command
cd $(sprout create feature-xyz --path)
```

### `sprout ls`
List all managed development environments with their status.

The output includes index numbers that can be used with other commands:
```bash
sprout ls
# Output:
# ┏━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
# ┃ No.  ┃ Branch          ┃ Path            ┃ Status ┃ Last Modified    ┃
# ┡━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
# │ 1    │ feature-auth    │ .sprout/feat... │        │ 2025-06-27 14:30 │
# │ 2    │ bugfix-api      │ .sprout/bugf... │        │ 2025-06-27 15:45 │
# └──────┴─────────────────┴─────────────────┴────────┴──────────────────┘
```

### `sprout rm <branch-name-or-index>`
Remove a development environment (with confirmation prompts).

You can use either the branch name or the index number from `sprout ls`:
```bash
# Remove by branch name
sprout rm feature-auth

# Remove by index number
sprout rm 1
```

### `sprout path <branch-name-or-index>`
Get the filesystem path of a development environment.

You can use either the branch name or the index number from `sprout ls`:
```bash
# Get path by branch name
sprout path feature-auth
# Output: /path/to/project/.sprout/feature-auth

# Get path by index number
sprout path 1
# Output: /path/to/project/.sprout/feature-auth

# Use with cd command
cd $(sprout path 2)
```

### `sprout --version`
Show the version of sprout.

## Template Syntax

sprout supports three types of placeholders in `.env.example`:

1. **Variable Placeholders**: `{{ VARIABLE_NAME }}`
   - **First**: Checks if the variable exists in your environment (e.g., `export API_KEY=xxx`)
   - **Then**: If not found in environment, prompts for user input
   - Example: `{{ API_KEY }}` will use `$API_KEY` if set, otherwise asks you to enter it

2. **Auto Port Assignment**: `{{ auto_port() }}`
   - Automatically assigns available ports
   - Avoids conflicts across ALL services in ALL sprout environments
   - Checks system port availability
   - Ensures global uniqueness even in monorepo setups

3. **Branch Name**: `{{ branch() }}`
   - Replaced with the current branch/subtree name
   - Useful for branch-specific configurations
   - Example: `SERVICE_NAME=myapp-{{ branch() }}` becomes `SERVICE_NAME=myapp-feature-auth`

4. **Docker Compose Syntax (Preserved)**: `${VARIABLE}`
   - NOT processed by sprout - passed through as-is
   - Useful for Docker Compose variable substitution
   - Example: `${DB_NAME:-default}` remains unchanged in generated `.env`

### Environment Variable Resolution Example

```bash
# Set environment variable
export API_KEY="my-secret-key"

# Create sprout environment - API_KEY will be automatically used
sprout create feature-branch
# → API_KEY in .env will be set to "my-secret-key" without prompting

# For unset variables, sprout will prompt
sprout create another-branch
# → Enter a value for 'DATABASE_URL': [user input required]
```

## Monorepo Tutorial

Try out the monorepo functionality with the included sample:

1. **Navigate to the sample monorepo**:
   ```bash
   cd sample/monorepo
   ```

2. **Set required environment variables**:
   ```bash
   export API_KEY="your-api-key"
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/myapp"
   export REACT_APP_API_KEY="your-frontend-api-key"
   export JWT_SECRET="your-jwt-secret"
   export SMTP_USER="your-smtp-username"
   export SMTP_PASS="your-smtp-password"
   ```

3. **Create a development environment**:
   ```bash
   sprout create monorepo-feature
   ```

4. **Navigate to the created environment**:
   ```bash
   cd .sprout/monorepo-feature
   ```

5. **Verify all services have unique ports**:
   ```bash
   find . -name "*.env" -exec echo "=== {} ===" \; -exec cat {} \;
   ```

6. **Start all services**:
   ```bash
   cd sample/monorepo
   docker-compose up -d
   ```

The sample includes:
- **Root service**: Database and Redis with shared configuration
- **Frontend**: React app with API integration
- **Backend**: REST API with authentication
- **Shared**: Utilities with message queue and monitoring

Each service gets unique, conflict-free ports automatically!

## Documentation

- [Architecture Overview](docs/sprout-cli/overview.md) - Design philosophy, architecture, and implementation details
- [Detailed Usage Guide](docs/sprout-cli/usage.md) - Comprehensive usage examples and troubleshooting

## Development

### Setup
```bash
# Install development dependencies
make setup
```

### Testing
```bash
# Run tests
make test

# Run tests with coverage
make test-cov
```

### Code Quality
```bash
# Run linter
make lint

# Format code
make format

# Run type checking
make typecheck
```

## Requirements

- Python 3.11+
- Git
- Docker Compose (optional, for Docker-based workflows)

## License

See LICENSE file.
