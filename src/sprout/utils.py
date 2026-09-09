"""Common utilities for sprout."""

import os
import random
import re
import socket
import subprocess
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

import typer
from rich.console import Console

from sprout.exceptions import SproutError
from sprout.types import BranchName, WorktreeInfo

# Type aliases
PortNumber: TypeAlias = int
PortSet: TypeAlias = set[PortNumber]

# Directory names skipped when scanning worktrees for .env files. These hold
# dependencies, caches and VCS internals, never a .env that sprout generated,
# but they can each contain tens of thousands of files. Descending into them
# turns a port scan into a multi-second walk on a real workspace.
SCAN_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".direnv",
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".terraform",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)

console = Console()


def is_git_repository() -> bool:
    """Check if current directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_git_root() -> Path:
    """Get the root directory of the git repository."""
    if not is_git_repository():
        raise SproutError("Not in a git repository")

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as e:
        raise SproutError(f"Command failed: {' '.join(cmd)}\n{e.stderr}") from e


def get_sprout_dir() -> Path:
    """Get the .sprout directory path."""
    return get_git_root() / ".sprout"


def ensure_sprout_dir() -> Path:
    """Ensure .sprout directory exists and return its path."""
    sprout_dir = get_sprout_dir()
    sprout_dir.mkdir(exist_ok=True)
    return sprout_dir


def _is_worktree_root(path: Path) -> bool:
    """Check whether a directory is a git worktree root.

    Args:
        path: Directory to inspect.
    """
    # git worktree add always leaves a .git entry: a file in a linked worktree,
    # a directory in a main checkout.
    return (path / ".git").exists()


def iter_env_files(root: Path) -> Iterator[Path]:
    """Yield .env files under root, skipping dependency and cache directories.

    An excluded name is still walked when the directory is a worktree root:
    a branch named "venv" or "fix/venv" puts a real worktree behind an excluded
    name, and skipping it would hand its ports out to the next worktree.

    Args:
        root: Directory to walk.

    Yields:
        Paths of the .env files found under root.
    """
    for dir_path, dir_names, file_names in os.walk(root):
        # Prune in place so os.walk does not descend into excluded directories
        dir_names[:] = [
            name
            for name in dir_names
            if name not in SCAN_EXCLUDED_DIRS or _is_worktree_root(Path(dir_path) / name)
        ]
        for file_name in file_names:
            if file_name.endswith(".env"):
                env_file = Path(dir_path) / file_name
                # Only regular files: a fifo named .env would block read_text()
                if env_file.is_file():
                    yield env_file


def get_used_ports() -> PortSet:
    """Get all ports currently used by sprout worktrees."""
    used_ports: PortSet = set()
    sprout_dir = get_sprout_dir()

    if not sprout_dir.exists():
        return used_ports

    # Scan all .env files recursively in .sprout/
    for env_file in iter_env_files(sprout_dir):
        try:
            content = env_file.read_text()
            # Find all port assignments (e.g., PORT=8080)
            port_matches = re.findall(r"=(\d{4,5})\b", content)
            for port_str in port_matches:
                port = int(port_str)
                if 1024 <= port <= 65535:
                    used_ports.add(port)
        except (OSError, ValueError):
            continue

    return used_ports


def is_port_available(port: PortNumber) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_available_port(used_ports: PortSet | None = None) -> PortNumber:
    """Find an available port that's not used by sprout or system.

    Args:
        used_ports: Ports to treat as taken, replacing the workspace scan rather
            than adding to it. Scanning every worktree is the expensive part of
            this call, so callers that allocate several ports in a row should
            scan once and pass the result instead of paying for a fresh walk per
            port. An empty set means nothing is taken; pass None to scan.
    """
    if used_ports is None:
        used_ports = get_used_ports()
    max_attempts = 1000

    for _ in range(max_attempts):
        # Random port between 1024 and 65535
        port = random.randint(1024, 65535)

        if port not in used_ports and is_port_available(port):
            return port

    raise SproutError("Could not find an available port after 1000 attempts")


def parse_env_template(
    template_path: Path,
    silent: bool = False,
    used_ports: PortSet | None = None,
    branch_name: str | None = None,
) -> str:
    """Parse .env.example template and process placeholders.

    Args:
        template_path: Path to the .env.example template file
        silent: If True, use stderr for prompts to keep stdout clean
        used_ports: Ports already in use across the workspace. The set replaces
            the workspace scan rather than adding to it, so passing a partial
            set silently gives up collision detection against the other
            worktrees. An empty set means nothing is taken; omit it to have this
            function scan once, and only if the template asks for a port.
        branch_name: Branch name to use for {{ branch() }} placeholders
    """
    if not template_path.exists():
        raise SproutError(f".env.example file not found at {template_path}")

    try:
        content = template_path.read_text()
    except OSError as e:
        raise SproutError(f"Failed to read .env.example: {e}") from e

    lines: list[str] = []
    # Ports that {{ auto_port() }} must avoid: the ones already taken across the
    # workspace plus the ones handed out earlier in this file. Left as None
    # until the first port is requested, so a template without auto_port() -
    # and every caller that already knows the used ports - never walks the
    # worktrees. Once filled, it is reused for the rest of the file.
    file_ports: PortSet | None = set(used_ports) if used_ports is not None else None

    for line in content.splitlines():
        # Process {{ auto_port() | default }} placeholders
        def replace_auto_port(match: re.Match[str]) -> str:
            # Extract default value if present (group 1)
            default_value = match.group(1)
            if default_value is not None:
                default_value = default_value.strip()

            # Generate available port. Scan the worktrees on the first
            # placeholder only; from then on file_ports carries both those
            # ports and the ones assigned earlier in this file.
            nonlocal file_ports
            if file_ports is None:
                file_ports = get_used_ports()
            port = find_available_port(file_ports)
            file_ports.add(port)
            return str(port)

        line = re.sub(r"{{\s*auto_port\(\)(?:\s*\|\s*([^}]*))?\s*}}", replace_auto_port, line)

        # Process {{ branch() | default }} placeholders
        def replace_branch(match: re.Match[str]) -> str:
            # Extract default value if present (group 1)
            default_value = match.group(1)
            if default_value is not None:
                default_value = default_value.strip()

            # Use branch_name if provided, otherwise use default
            if branch_name:
                return branch_name
            elif default_value is not None:
                return default_value
            else:
                # No branch name and no default - keep placeholder unchanged
                return match.group(0)

        line = re.sub(r"{{\s*branch\(\)(?:\s*\|\s*([^}]*))?\s*}}", replace_branch, line)

        # Process {{ VARIABLE | default }} placeholders
        def replace_variable(match: re.Match[str]) -> str:
            var_name = match.group(1).strip()
            # Extract default value if present (group 2)
            default_value = match.group(2)
            if default_value is not None:
                default_value = default_value.strip()

            # Check environment variable first
            value = os.environ.get(var_name)
            if value is None:
                # If default value is provided, use it
                if default_value is not None:
                    return default_value

                # No default value - prompt user for value
                # Create a relative path for display
                try:
                    display_path = template_path.relative_to(Path.cwd())
                except ValueError:
                    display_path = template_path

                # Prompt user for value with file context
                if silent:
                    # Use stderr for prompts in silent mode to keep stdout clean
                    prompt = f"Enter a value for '{var_name}' (from {display_path}): "
                    typer.echo(prompt, err=True, nl=False)
                    value = input()
                else:
                    prompt = (
                        f"Enter a value for '[cyan]{var_name}[/cyan]' "
                        f"(from [dim]{display_path}[/dim]): "
                    )
                    value = console.input(prompt)
            return value

        # Only match variables that don't look like function calls (no parentheses)
        # Now also captures optional | default_value
        line = re.sub(r"{{\s*([^}()]+?)(?:\s*\|\s*([^}]*))?\s*}}", replace_variable, line)

        lines.append(line)

    return "\n".join(lines)


def worktree_exists(branch_name: BranchName) -> bool:
    """Check if a worktree already exists for the given branch."""
    worktree_path = get_sprout_dir() / branch_name
    return worktree_path.exists()


def branch_exists(branch_name: BranchName) -> bool:
    """Check if a git branch exists."""
    result = run_command(["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"], check=False)
    return result.returncode == 0


def get_indexed_worktrees() -> list[WorktreeInfo]:
    """Get a list of sprout-managed worktrees with consistent ordering.

    Returns:
        List of WorktreeInfo dicts, sorted by branch name for consistent indexing.
    """
    if not is_git_repository():
        raise SproutError("Not in a git repository")

    sprout_dir = get_sprout_dir()

    # Get worktree list from git
    result = run_command(["git", "worktree", "list", "--porcelain"])

    # Parse worktree output
    worktrees: list[WorktreeInfo] = []
    current_worktree: WorktreeInfo = {}

    for line in result.stdout.strip().split("\n"):
        if not line:
            if current_worktree:
                worktrees.append(current_worktree)
                current_worktree = {}
            continue

        if line.startswith("worktree "):
            current_worktree["path"] = Path(line[9:])
        elif line.startswith("branch "):
            branch_ref = line[7:]
            # Strip refs/heads/ prefix if present
            if branch_ref.startswith("refs/heads/"):
                current_worktree["branch"] = branch_ref[11:]
            else:
                current_worktree["branch"] = branch_ref
        elif line.startswith("HEAD "):
            current_worktree["head"] = line[5:]

    if current_worktree:
        worktrees.append(current_worktree)

    # Filter for sprout-managed worktrees
    sprout_worktrees: list[WorktreeInfo] = []
    current_path = Path.cwd().resolve()

    for wt in worktrees:
        wt_path = wt["path"].resolve()
        if wt_path.parent == sprout_dir:
            # Check if we're currently in this worktree
            wt["is_current"] = current_path == wt_path or current_path.is_relative_to(wt_path)

            # Get last modified time
            if wt_path.exists():
                stat = wt_path.stat()
                wt["modified"] = datetime.fromtimestamp(stat.st_mtime)
            else:
                wt["modified"] = None

            sprout_worktrees.append(wt)

    # Sort by branch name for consistent indexing
    sprout_worktrees.sort(key=lambda wt: wt.get("branch") or wt.get("head") or "")

    return sprout_worktrees


def resolve_branch_identifier(identifier: str) -> BranchName | None:
    """Resolve a branch identifier (name or index) to a branch name.

    Args:
        identifier: Either a branch name or a 1-based index number

    Returns:
        Branch name if found, None otherwise
    """
    # Check if identifier is a number
    if identifier.isdigit():
        index = int(identifier)
        worktrees = get_indexed_worktrees()

        if 1 <= index <= len(worktrees):
            return worktrees[index - 1].get("branch", worktrees[index - 1].get("head", ""))
        return None

    # Otherwise treat as branch name
    return identifier
