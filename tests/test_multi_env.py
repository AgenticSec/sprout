"""Tests for multiple .env.example files functionality."""

import subprocess

from typer.testing import CliRunner

import sprout.utils
from sprout.cli import app
from sprout.utils import get_used_ports

from .test_integration import git_repo  # noqa: F401

runner = CliRunner()


class TestMultipleEnvExamples:
    """Test handling of multiple .env.example files."""

    def test_create_with_multiple_env_examples(self, git_repo, monkeypatch):  # noqa: F811
        """Test creating worktree with multiple .env.example files."""
        git_repo, default_branch = git_repo
        monkeypatch.chdir(git_repo)
        monkeypatch.setenv("API_KEY", "test_key")
        monkeypatch.setenv("DB_PASSWORD", "test_password")

        # Create service directories with .env.example files
        service_a = git_repo / "service-a"
        service_a.mkdir()
        (service_a / ".env.example").write_text("""# Service A Configuration
API_KEY={{ API_KEY }}
API_PORT={{ auto_port() }}
""")

        service_b = git_repo / "service-b"
        service_b.mkdir()
        (service_b / ".env.example").write_text("""# Service B Configuration
DB_PASSWORD={{ DB_PASSWORD }}
DB_PORT={{ auto_port() }}
""")

        # Add files to git
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add services"], cwd=git_repo, check=True)

        # Create worktree
        result = runner.invoke(app, ["create", "feature-multi"])
        assert result.exit_code == 0
        assert "Generating .env files from 3 template(s)" in result.stdout

        # Check that all .env files were created with correct structure
        worktree_path = git_repo / ".sprout" / "feature-multi"
        assert (worktree_path / ".env").exists()
        assert (worktree_path / "service-a" / ".env").exists()
        assert (worktree_path / "service-b" / ".env").exists()

        # Check content
        root_env = (worktree_path / ".env").read_text()
        assert "API_KEY=test_key" in root_env

        service_a_env = (worktree_path / "service-a" / ".env").read_text()
        assert "API_KEY=test_key" in service_a_env
        assert "API_PORT=" in service_a_env

        service_b_env = (worktree_path / "service-b" / ".env").read_text()
        assert "DB_PASSWORD=test_password" in service_b_env
        assert "DB_PORT=" in service_b_env

    def test_port_uniqueness_across_services(self, git_repo, monkeypatch):  # noqa: F811
        """Test that auto_port() generates unique ports across all services."""
        git_repo, default_branch = git_repo
        monkeypatch.chdir(git_repo)
        monkeypatch.setenv("API_KEY", "test_key")  # Set env var for root .env.example

        # Create multiple services with port requirements
        for i in range(3):
            service_dir = git_repo / f"service-{i}"
            service_dir.mkdir()
            (service_dir / ".env.example").write_text(f"""# Service {i}
PORT1={{{{ auto_port() }}}}
PORT2={{{{ auto_port() }}}}
""")

        # Add files to git
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add services"], cwd=git_repo, check=True)

        # Create worktree
        result = runner.invoke(app, ["create", "test-ports"])
        assert result.exit_code == 0

        # Collect all ports
        all_ports = set()
        worktree_path = git_repo / ".sprout" / "test-ports"

        for i in range(3):
            env_content = (worktree_path / f"service-{i}" / ".env").read_text()
            lines = env_content.strip().split("\n")
            for line in lines:
                if "=" in line and not line.startswith("#"):
                    port = int(line.split("=")[1])
                    assert port not in all_ports, f"Port {port} is duplicated"
                    all_ports.add(port)

        # Should have 6 unique ports (2 per service × 3 services)
        assert len(all_ports) == 6

    def test_global_port_uniqueness_across_worktrees(self, git_repo, monkeypatch):  # noqa: F811
        """Test that ports are unique across different worktrees."""
        git_repo, default_branch = git_repo
        monkeypatch.chdir(git_repo)
        monkeypatch.setenv("API_KEY", "test_key")  # Set env var for root .env.example

        # Create service with ports
        service_dir = git_repo / "service"
        service_dir.mkdir()
        (service_dir / ".env.example").write_text("""
PORT1={{ auto_port() }}
PORT2={{ auto_port() }}
""")

        # Add files to git
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add service"], cwd=git_repo, check=True)

        # Create first worktree
        result = runner.invoke(app, ["create", "branch1"])
        assert result.exit_code == 0

        # Get ports from first worktree
        env1 = (git_repo / ".sprout" / "branch1" / "service" / ".env").read_text()
        ports1 = set()
        for line in env1.strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                ports1.add(int(line.split("=")[1]))

        # Create second worktree
        result = runner.invoke(app, ["create", "branch2"])
        assert result.exit_code == 0

        # Get ports from second worktree
        env2 = (git_repo / ".sprout" / "branch2" / "service" / ".env").read_text()
        ports2 = set()
        for line in env2.strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                ports2.add(int(line.split("=")[1]))

        # Ensure no overlap
        assert len(ports1.intersection(ports2)) == 0, "Ports should not overlap between worktrees"

    def test_create_scans_the_workspace_once(self, git_repo, monkeypatch, mocker):  # noqa: F811
        """Test one create walks the worktrees once, not once per port."""
        git_repo, _default_branch = git_repo
        monkeypatch.chdir(git_repo)
        monkeypatch.setenv("API_KEY", "test_key")  # Set env var for root .env.example

        service = git_repo / "service"
        service.mkdir()
        (service / ".env.example").write_text(
            "P1={{ auto_port() }}\nP2={{ auto_port() }}\nP3={{ auto_port() }}\n"
        )
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add service"], cwd=git_repo, check=True)

        # Every scan funnels through iter_env_files, whichever module asked for it
        spy = mocker.spy(sprout.utils, "iter_env_files")

        result = runner.invoke(app, ["create", "scan-once"])

        assert result.exit_code == 0
        assert spy.call_count == 1

    def test_nested_directory_structure(self, git_repo, monkeypatch):  # noqa: F811
        """Test handling of nested directory structures."""
        git_repo, default_branch = git_repo
        monkeypatch.chdir(git_repo)
        monkeypatch.setenv("API_KEY", "test_key")  # Set env var for root .env.example

        # Create nested structure
        nested_path = git_repo / "services" / "backend" / "api"
        nested_path.mkdir(parents=True)
        (nested_path / ".env.example").write_text("NESTED_PORT={{ auto_port() }}")

        # Add files to git
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add nested service"], cwd=git_repo, check=True)

        # Create worktree
        result = runner.invoke(app, ["create", "nested-test"])
        assert result.exit_code == 0

        # Check nested .env was created
        worktree_path = git_repo / ".sprout" / "nested-test"
        nested_env_path = worktree_path / "services" / "backend" / "api" / ".env"
        assert nested_env_path.exists()
        assert "NESTED_PORT=" in nested_env_path.read_text()

    def test_get_used_ports_recursive(self, tmp_path, monkeypatch):
        """Test that get_used_ports now searches recursively."""
        monkeypatch.setattr("sprout.utils.get_sprout_dir", lambda: tmp_path)

        # Create nested structure with .env files
        (tmp_path / "branch1").mkdir()
        (tmp_path / "branch1" / ".env").write_text("PORT1=8080")

        (tmp_path / "branch1" / "service-a").mkdir()
        (tmp_path / "branch1" / "service-a" / ".env").write_text("PORT2=8081")

        (tmp_path / "branch2" / "nested" / "deep").mkdir(parents=True)
        (tmp_path / "branch2" / "nested" / "deep" / ".env").write_text("PORT3=8082")

        # Test recursive port collection
        ports = get_used_ports()
        assert ports == {8080, 8081, 8082}
