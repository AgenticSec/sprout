# sprout Usage Guide

## Installation

```bash
# From PyPI (when published)
pip install sprout

# Development installation
git clone https://github.com/AgenticSec/sprout.git
cd sprout
pip install -e ".[dev]"
```

## Basic Usage

### 1. Create New Development Environment

```bash
sprout create feature-branch
```

This command performs:
1. Creates worktree in `.sprout/feature-branch`
2. Generates `.env` from `.env.example` template (if template exists)
3. Prompts for required environment variables (if `.env.example` exists)
4. Automatically assigns port numbers (if `.env.example` exists)

**Note**: If no `.env.example` files are found, sprout will show a warning but continue creating the worktree without `.env` generation.

### 2. List Development Environments

```bash
sprout ls
```

Example output:
```
                    Sprout Worktrees                    
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Branch        ┃ Path                    ┃ Status   ┃ Last Modified   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ feature-auth  │ .sprout/feature-auth    │ ● current│ 2024-01-15 14:30│
├───────────────┼─────────────────────────┼──────────┼─────────────────┤
│ feature-ui    │ .sprout/feature-ui      │          │ 2024-01-14 10:15│
└───────────────┴─────────────────────────┴──────────┴─────────────────┘
```

### 3. Remove Development Environment

```bash
sprout rm feature-branch
```

Displays confirmation prompts:
- Worktree removal confirmation
- Git branch removal confirmation (optional)

### 4. Get Development Environment Path

```bash
# Display path
sprout path feature-branch

# Navigate directly
cd $(sprout path feature-branch)
```

### 5. Show Version

```bash
sprout --version
```

## Writing .env.example Templates

### Basic Environment Variables
```env
DATABASE_URL={{ DATABASE_URL }}
API_KEY={{ API_KEY }}
```

### Automatic Port Assignment
```env
WEB_PORT={{ auto_port() }}
API_PORT={{ auto_port() }}
DB_PORT={{ auto_port() }}
```

### Docker Compose Variables (Preserved As-Is)
```env
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-myproject}
```

### Fixed Values
```env
ENVIRONMENT=development
DEBUG=true
```

## Environment Variable Resolution

sprout resolves environment variables in the following priority order:

1. **System Environment Variables** - If a variable is already set in your shell environment (e.g., `export API_KEY=xxx`), it will be used automatically without prompting
2. **User Input** - If not found in the environment, sprout will prompt you to enter the value
3. **auto_port()** - Special function that automatically finds available ports, avoiding conflicts with other sprout environments

## Practical Examples

### 1. Running Multiple Development Environments in Parallel

```bash
# Develop authentication feature
sprout create feature-auth
cd .sprout/feature-auth
docker compose up -d

# Develop UI improvements (in another terminal)
sprout create feature-ui  
cd .sprout/feature-ui
docker compose up -d

# Ports are automatically assigned different numbers
```

### 2. Pre-setting Environment Variables

```bash
# Set environment variables in shell
export API_KEY="my-secret-key"
export DATABASE_URL="postgres://localhost/mydb"

# sprout automatically uses these values
sprout create feature-branch
```

### 3. Switching Between Branches

```bash
# Check current environment
sprout ls

# Navigate to another environment
cd $(sprout path another-branch)
```

### 4. Working with Existing Branches

```bash
# Create worktree for existing remote branch
sprout create existing-feature

# sprout will automatically check out the existing branch
# if it exists on the remote
```

## Port Management

sprout intelligently manages ports to avoid conflicts:

- Scans existing `.sprout/*/` directories for used ports
- Checks system port availability
- Automatically assigns ports starting from 3000
- Each `{{ auto_port() }}` gets a unique port

Example with multiple services:
```env
# .env.example
WEB_PORT={{ auto_port() }}      # Might assign 3000
API_PORT={{ auto_port() }}      # Might assign 3001
DB_PORT={{ auto_port() }}       # Might assign 3002
REDIS_PORT={{ auto_port() }}    # Might assign 3003
```

## Troubleshooting

### "Not in a git repository" Error
- Execute from Git repository root directory
- Ensure `.git` directory exists

### Working Without .env.example Files
As of recent versions, sprout works perfectly fine without `.env.example` files:
- If no `.env.example` files exist, sprout will show a warning but continue
- The worktree will be created successfully without `.env` generation
- This is useful for projects that don't need environment variable templating

If you want to add `.env` generation later:
- Create `.env.example` in project root or subdirectories  
- Use the template syntax described above

### "Could not find an available port" Error
- Occurs when many ports are in use
- Stop unnecessary services
- Check for stale `.sprout/` directories

### Cannot Delete Worktree
- Process might be running in that directory
- Move out of directory and retry
- Check for running Docker containers: `docker compose down`

### "Worktree already exists" Error
- A worktree for this branch already exists
- Use `sprout ls` to see existing worktrees
- Remove with `sprout rm branch-name` if needed

### Port Already in Use
- Another application is using the assigned port
- Stop the conflicting application
- Or manually edit `.env` to use a different port

## Best Practices

1. **Branch Naming**: Use descriptive branch names that reflect the feature
2. **Environment Variables**: Store sensitive values in your shell profile, not in the repository
3. **Cleanup**: Regularly remove unused worktrees with `sprout rm`
4. **Port Ranges**: Reserve port ranges for different services (e.g., 3000-3099 for web, 5000-5099 for APIs)

## Integration with CI/CD

While sprout is primarily for local development, you can use similar patterns in CI:

```yaml
# Example GitHub Actions
- name: Setup environment
  run: |
    cp .env.example .env
    sed -i 's/{{ auto_port() }}/3000/g' .env
    sed -i 's/{{ API_KEY }}/${{ secrets.API_KEY }}/g' .env
```