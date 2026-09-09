"""Tests for utility functions."""

import os
import socket
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from sprout.exceptions import SproutError
from sprout.utils import (
    branch_exists,
    find_available_port,
    get_git_root,
    get_used_ports,
    is_git_repository,
    is_port_available,
    parse_env_template,
    run_command,
    worktree_exists,
)


class TestGitUtils:
    """Test git-related utility functions."""

    def test_is_git_repository_true(self, mocker):
        """Test is_git_repository returns True in a git repo."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0)

        assert is_git_repository() is True
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_is_git_repository_false(self, mocker):
        """Test is_git_repository returns False outside a git repo."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=1)

        assert is_git_repository() is False

    def test_get_git_root_success(self, mocker):
        """Test get_git_root returns the repository root."""
        mocker.patch("sprout.utils.is_git_repository", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="/home/user/project\n")

        root = get_git_root()
        assert root == Path("/home/user/project")

    def test_get_git_root_not_in_repo(self, mocker):
        """Test get_git_root raises error when not in a repo."""
        mocker.patch("sprout.utils.is_git_repository", return_value=False)

        with pytest.raises(SproutError, match="Not in a git repository"):
            get_git_root()

    def test_branch_exists_true(self, mocker):
        """Test branch_exists returns True for existing branch."""
        mock_run = mocker.patch("sprout.utils.run_command")
        mock_run.return_value = Mock(returncode=0)

        assert branch_exists("main") is True

    def test_branch_exists_false(self, mocker):
        """Test branch_exists returns False for non-existing branch."""
        mock_run = mocker.patch("sprout.utils.run_command")
        mock_run.return_value = Mock(returncode=1)

        assert branch_exists("nonexistent") is False


class TestPortUtils:
    """Test port-related utility functions."""

    def test_get_used_ports(self, tmp_path, mocker):
        """Test get_used_ports extracts ports from .env files."""
        mocker.patch("sprout.utils.get_sprout_dir", return_value=tmp_path)

        # Create test .env files
        (tmp_path / "branch1").mkdir()
        (tmp_path / "branch1" / ".env").write_text("WEB_PORT=8080\nDB_PORT=5432\nNOT_A_PORT=abc")

        (tmp_path / "branch2").mkdir()
        (tmp_path / "branch2" / ".env").write_text("API_PORT=3000")

        ports = get_used_ports()
        assert ports == {8080, 5432, 3000}

    def test_get_used_ports_empty(self, tmp_path, mocker):
        """Test get_used_ports returns empty set when no .env files."""
        mocker.patch("sprout.utils.get_sprout_dir", return_value=tmp_path)

        ports = get_used_ports()
        assert ports == set()

    def test_is_port_available_true(self):
        """Test is_port_available returns True for free port."""
        # Find a likely free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        assert is_port_available(port) is True

    def test_is_port_available_false(self):
        """Test is_port_available returns False for occupied port."""
        # Occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

            # Test while port is occupied
            assert is_port_available(port) is False

    def test_find_available_port(self, mocker):
        """Test find_available_port returns an available port."""
        mocker.patch("sprout.utils.get_used_ports", return_value={8080, 8081})
        mocker.patch("sprout.utils.is_port_available", side_effect=[False, False, True])
        # Need more values for the loop to work properly
        mocker.patch("random.randint", side_effect=[8080, 8081, 8082] * 100)

        port = find_available_port()
        assert port == 8082

    def test_find_available_port_exhausted(self, mocker):
        """Test find_available_port raises error after max attempts."""
        mocker.patch("sprout.utils.get_used_ports", return_value=set())
        mocker.patch("sprout.utils.is_port_available", return_value=False)

        with pytest.raises(SproutError, match="Could not find an available port"):
            find_available_port()

    def test_get_used_ports_skips_dependency_directories(self, tmp_path, mocker):
        """Test get_used_ports ignores .env files under dependency directories."""
        mocker.patch("sprout.utils.get_sprout_dir", return_value=tmp_path)

        (tmp_path / "branch1").mkdir()
        (tmp_path / "branch1" / ".env").write_text("WEB_PORT=8080")

        # Dependency and cache trees can ship their own .env files, and walking
        # them is what made port allocation slow on large worktrees.
        vendored = tmp_path / "branch1" / "node_modules" / "some-package"
        vendored.mkdir(parents=True)
        (vendored / ".env").write_text("VENDOR_PORT=9999")

        virtualenv = tmp_path / "branch1" / ".venv" / "lib"
        virtualenv.mkdir(parents=True)
        (virtualenv / ".env").write_text("VENV_PORT=9998")

        assert get_used_ports() == {8080}

    def test_find_available_port_accepts_precomputed_ports(self, mocker):
        """Test find_available_port skips the workspace scan when given ports."""
        scan = mocker.patch("sprout.utils.get_used_ports", return_value=set())
        mocker.patch("sprout.utils.is_port_available", return_value=True)
        mocker.patch("random.randint", side_effect=[8080, 8081])

        port = find_available_port({8080})

        assert port == 8081
        scan.assert_not_called()


class TestEnvTemplateParser:
    """Test .env template parsing."""

    def test_parse_env_template_auto_port(self, tmp_path, mocker):
        """Test parsing {{ auto_port() }} placeholders."""
        mocker.patch("sprout.utils.find_available_port", side_effect=[8080, 3000])

        template = tmp_path / ".env.example"
        template.write_text("WEB_PORT={{ auto_port() }}\nAPI_PORT={{auto_port()}}")

        result = parse_env_template(template)
        assert result == "WEB_PORT=8080\nAPI_PORT=3000"

    def test_parse_env_template_scans_workspace_once(self, tmp_path, mocker):
        """Test the workspace is scanned once, not once per auto_port()."""
        scan = mocker.patch("sprout.utils.get_used_ports", return_value=set())
        mocker.patch("sprout.utils.is_port_available", return_value=True)
        mocker.patch("random.randint", side_effect=[8080, 8081, 8082])

        template = tmp_path / ".env.example"
        template.write_text(
            "A_PORT={{ auto_port() }}\nB_PORT={{ auto_port() }}\nC_PORT={{ auto_port() }}"
        )

        result = parse_env_template(template)

        assert result == "A_PORT=8080\nB_PORT=8081\nC_PORT=8082"
        assert scan.call_count == 1

    def test_parse_env_template_reuses_given_used_ports(self, tmp_path, mocker):
        """Test a caller-supplied port set replaces the workspace scan."""
        scan = mocker.patch("sprout.utils.get_used_ports", return_value=set())
        mocker.patch("sprout.utils.is_port_available", return_value=True)
        mocker.patch("random.randint", side_effect=[8080, 8081])

        template = tmp_path / ".env.example"
        template.write_text("WEB_PORT={{ auto_port() }}")

        result = parse_env_template(template, used_ports={8080})

        assert result == "WEB_PORT=8081"
        scan.assert_not_called()

    def test_parse_env_template_variable_from_env(self, tmp_path, mocker):
        """Test parsing {{ VARIABLE }} from environment."""
        mocker.patch.dict(os.environ, {"API_KEY": "secret123"})

        template = tmp_path / ".env.example"
        template.write_text("API_KEY={{ API_KEY }}")

        result = parse_env_template(template)
        assert result == "API_KEY=secret123"

    def test_parse_env_template_variable_from_input(self, tmp_path, mocker):
        """Test parsing {{ VARIABLE }} from user input."""
        mocker.patch("sprout.utils.console.input", return_value="user_input")

        template = tmp_path / ".env.example"
        template.write_text("DB_PASSWORD={{ DB_PASSWORD }}")

        result = parse_env_template(template)
        assert result == "DB_PASSWORD=user_input"

    def test_parse_env_template_preserves_docker_syntax(self, tmp_path):
        """Test that ${...} syntax is preserved."""
        template = tmp_path / ".env.example"
        template.write_text("COMPOSE_VAR=${COMPOSE_VAR:-default}")

        result = parse_env_template(template)
        assert result == "COMPOSE_VAR=${COMPOSE_VAR:-default}"

    def test_parse_env_template_branch_placeholder(self, tmp_path):
        """Test parsing {{ branch() }} placeholders."""
        template = tmp_path / ".env.example"
        template.write_text("BRANCH_NAME={{ branch() }}\nFEATURE={{ branch() }}_feature")

        result = parse_env_template(template, branch_name="feature-auth")
        assert result == "BRANCH_NAME=feature-auth\nFEATURE=feature-auth_feature"

    def test_parse_env_template_branch_placeholder_none(self, tmp_path):
        """Test {{ branch() }} placeholder when branch_name is None."""
        template = tmp_path / ".env.example"
        template.write_text("BRANCH={{ branch() }}")

        # When branch_name is None, placeholder should remain unchanged
        result = parse_env_template(template, branch_name=None)
        assert result == "BRANCH={{ branch() }}"

    def test_parse_env_template_mixed_placeholders(self, tmp_path, mocker):
        """Test parsing mixed placeholders in one template."""
        mocker.patch("sprout.utils.find_available_port", return_value=8080)
        mocker.patch.dict(os.environ, {"API_KEY": "secret"})
        mocker.patch("sprout.utils.console.input", return_value="password123")

        template = tmp_path / ".env.example"
        template.write_text(
            "API_KEY={{ API_KEY }}\n"
            "PORT={{ auto_port() }}\n"
            "BRANCH={{ branch() }}\n"
            "DB_PASS={{ DB_PASS }}\n"
            "COMPOSE_VAR=${COMPOSE_VAR}"
        )

        result = parse_env_template(template, branch_name="feature-xyz")
        assert result == (
            "API_KEY=secret\n"
            "PORT=8080\n"
            "BRANCH=feature-xyz\n"
            "DB_PASS=password123\n"
            "COMPOSE_VAR=${COMPOSE_VAR}"
        )

    def test_parse_env_template_variable_with_default(self, tmp_path, mocker):
        """Test parsing {{ VARIABLE | default }} when variable is not set."""
        # Ensure the variable is not in environment
        mocker.patch.dict(os.environ, {}, clear=False)
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        template = tmp_path / ".env.example"
        template.write_text("TEST_VAR={{ TEST_VAR | localhost }}")

        result = parse_env_template(template)
        assert result == "TEST_VAR=localhost"

    def test_parse_env_template_variable_with_default_env_set(self, tmp_path, mocker):
        """Test that environment variable overrides default value."""
        mocker.patch.dict(os.environ, {"TEST_VAR": "custom_value"})

        template = tmp_path / ".env.example"
        template.write_text("TEST_VAR={{ TEST_VAR | localhost }}")

        result = parse_env_template(template)
        assert result == "TEST_VAR=custom_value"

    def test_parse_env_template_variable_with_empty_default(self, tmp_path, mocker):
        """Test parsing {{ VARIABLE | }} with empty string as default."""
        mocker.patch.dict(os.environ, {}, clear=False)
        if "EMPTY_VAR" in os.environ:
            del os.environ["EMPTY_VAR"]

        template = tmp_path / ".env.example"
        template.write_text("EMPTY_VAR={{ EMPTY_VAR | }}")

        result = parse_env_template(template)
        assert result == "EMPTY_VAR="

    def test_parse_env_template_variable_whitespace_trimming(self, tmp_path, mocker):
        """Test that whitespace is trimmed from default values."""
        mocker.patch.dict(os.environ, {}, clear=False)
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        template = tmp_path / ".env.example"
        template.write_text("TEST_VAR={{ TEST_VAR |   localhost   }}")

        result = parse_env_template(template)
        assert result == "TEST_VAR=localhost"

    def test_parse_env_template_branch_with_default(self, tmp_path):
        """Test parsing {{ branch() | default }} when branch_name is None."""
        template = tmp_path / ".env.example"
        template.write_text("BRANCH={{ branch() | main }}")

        result = parse_env_template(template, branch_name=None)
        assert result == "BRANCH=main"

    def test_parse_env_template_branch_with_default_branch_set(self, tmp_path):
        """Test that branch_name overrides default value."""
        template = tmp_path / ".env.example"
        template.write_text("BRANCH={{ branch() | main }}")

        result = parse_env_template(template, branch_name="feature-xyz")
        assert result == "BRANCH=feature-xyz"

    def test_parse_env_template_auto_port_with_default(self, tmp_path, mocker):
        """Test {{ auto_port() | default }} - default is captured but not used."""
        mocker.patch("sprout.utils.find_available_port", return_value=9000)

        template = tmp_path / ".env.example"
        template.write_text("PORT={{ auto_port() | 8080 }}")

        # auto_port() always generates a port, so default is not used
        result = parse_env_template(template)
        assert result == "PORT=9000"

    def test_parse_env_template_mixed_with_defaults(self, tmp_path, mocker):
        """Test parsing mixed placeholders with default values."""
        mocker.patch("sprout.utils.find_available_port", return_value=8080)
        mocker.patch.dict(os.environ, {"SET_VAR": "from_env"}, clear=False)
        if "UNSET_VAR" in os.environ:
            del os.environ["UNSET_VAR"]

        template = tmp_path / ".env.example"
        template.write_text(
            "SET_VAR={{ SET_VAR | default1 }}\n"
            "UNSET_VAR={{ UNSET_VAR | default2 }}\n"
            "PORT={{ auto_port() | 3000 }}\n"
            "BRANCH={{ branch() | develop }}\n"
            "EMPTY={{ EMPTY | }}"
        )

        result = parse_env_template(template, branch_name=None)
        assert result == ("SET_VAR=from_env\nUNSET_VAR=default2\nPORT=8080\nBRANCH=develop\nEMPTY=")

    def test_parse_env_template_file_not_found(self, tmp_path):
        """Test error when template file doesn't exist."""
        template = tmp_path / "nonexistent.env"

        with pytest.raises(SproutError, match=".env.example file not found"):
            parse_env_template(template)


class TestWorktreeUtils:
    """Test worktree-related utilities."""

    def test_worktree_exists_true(self, tmp_path, mocker):
        """Test worktree_exists returns True when directory exists."""
        mocker.patch("sprout.utils.get_sprout_dir", return_value=tmp_path)
        (tmp_path / "feature-branch").mkdir()

        assert worktree_exists("feature-branch") is True

    def test_worktree_exists_false(self, tmp_path, mocker):
        """Test worktree_exists returns False when directory doesn't exist."""
        mocker.patch("sprout.utils.get_sprout_dir", return_value=tmp_path)

        assert worktree_exists("nonexistent") is False


class TestCommandRunner:
    """Test command execution utilities."""

    def test_run_command_success(self, mocker):
        """Test run_command returns result on success."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="success",
            stderr="",
        )

        result = run_command(["echo", "test"])
        assert result.stdout == "success"

    def test_run_command_failure(self, mocker):
        """Test run_command raises error on failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["git", "status"], stderr="error message"
        )

        with pytest.raises(SproutError, match="Command failed"):
            run_command(["git", "status"])


class TestIndexedWorktrees:
    """Test indexed worktree functionality."""

    def test_get_indexed_worktrees(self, mocker, tmp_path):
        """Test get_indexed_worktrees returns sorted list."""
        sprout_dir = tmp_path / ".sprout"
        sprout_dir.mkdir()

        # Create test directories
        feature_b_dir = sprout_dir / "feature-b"
        feature_b_dir.mkdir()
        feature_a_dir = sprout_dir / "feature-a"
        feature_a_dir.mkdir()

        mocker.patch("sprout.utils.is_git_repository", return_value=True)
        mocker.patch("sprout.utils.get_sprout_dir", return_value=sprout_dir)
        mocker.patch("pathlib.Path.cwd", return_value=tmp_path)

        # Mock git worktree list output (unsorted)
        mock_result = Mock()
        mock_result.stdout = f"""worktree {feature_b_dir}
HEAD def456
branch refs/heads/feature-b

worktree {feature_a_dir}
HEAD abc123
branch refs/heads/feature-a
"""
        mocker.patch("sprout.utils.run_command", return_value=mock_result)

        from sprout.utils import get_indexed_worktrees

        worktrees = get_indexed_worktrees()

        assert len(worktrees) == 2
        # Check that they're sorted by branch name
        assert worktrees[0]["branch"] == "feature-a"
        assert worktrees[1]["branch"] == "feature-b"

    def test_resolve_branch_identifier_with_name(self):
        """Test resolve_branch_identifier with branch name."""
        from sprout.utils import resolve_branch_identifier

        result = resolve_branch_identifier("feature-branch")
        assert result == "feature-branch"

    def test_resolve_branch_identifier_with_valid_index(self, mocker, tmp_path):
        """Test resolve_branch_identifier with valid index."""
        sprout_dir = tmp_path / ".sprout"
        sprout_dir.mkdir()
        feature_dir = sprout_dir / "feature-a"
        feature_dir.mkdir()

        mocker.patch("sprout.utils.is_git_repository", return_value=True)
        mocker.patch("sprout.utils.get_sprout_dir", return_value=sprout_dir)
        mocker.patch("pathlib.Path.cwd", return_value=tmp_path)

        mock_result = Mock()
        mock_result.stdout = f"""worktree {feature_dir}
HEAD abc123
branch refs/heads/feature-a
"""
        mocker.patch("sprout.utils.run_command", return_value=mock_result)

        from sprout.utils import resolve_branch_identifier

        result = resolve_branch_identifier("1")
        assert result == "feature-a"

    def test_resolve_branch_identifier_with_invalid_index(self, mocker):
        """Test resolve_branch_identifier with invalid index."""
        mocker.patch("sprout.utils.is_git_repository", return_value=True)
        mocker.patch("sprout.utils.get_sprout_dir", return_value=Path("/project/.sprout"))

        mock_result = Mock()
        mock_result.stdout = ""  # No worktrees
        mocker.patch("sprout.utils.run_command", return_value=mock_result)

        from sprout.utils import resolve_branch_identifier

        result = resolve_branch_identifier("99")
        assert result is None
