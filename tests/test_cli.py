"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from jacobs_ladder.cli import cli
from jacobs_ladder.discovery import Instance


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_buffers(tmp_path):
    buffers = tmp_path / "buffers"
    buffers.mkdir()
    return buffers


class TestDiscover:
    def test_lists_active_instances(self, runner):
        instances = [
            Instance(name="my-api", pid=1234, cwd="/home/user/projects/my-api"),
            Instance(name="my-client", pid=5678, cwd="/home/user/projects/my-client"),
        ]
        with patch("jacobs_ladder.cli.discover_instances", return_value=instances):
            result = runner.invoke(cli, ["discover"])

        assert result.exit_code == 0
        assert "my-api" in result.output
        assert "my-client" in result.output
        assert "1234" in result.output

    def test_no_instances_message(self, runner):
        with patch("jacobs_ladder.cli.discover_instances", return_value=[]):
            result = runner.invoke(cli, ["discover"])

        assert result.exit_code == 0
        assert "No other Claude agents running" in result.output


class TestPublish:
    def test_publishes_inline_message(self, runner, tmp_buffers):
        instances = [Instance(name="my-client", pid=5678, cwd="/projects/my-client")]
        with (
            patch("jacobs_ladder.cli.discover_instances", return_value=instances),
            patch("jacobs_ladder.cli.BUFFERS_DIR", tmp_buffers),
        ):
            result = runner.invoke(
                cli, ["publish", "--to", "my-client", "--message", "schema updated"]
            )

        assert result.exit_code == 0
        assert "Published" in result.output
        buffer_file = tmp_buffers / "my-client.md"
        assert buffer_file.exists()
        assert "schema updated" in buffer_file.read_text()

    def test_rejects_unknown_target(self, runner):
        with patch("jacobs_ladder.cli.discover_instances", return_value=[]):
            result = runner.invoke(
                cli, ["publish", "--to", "nonexistent", "--message", "hello"]
            )

        assert result.exit_code != 0 or "not running" in result.output


class TestPull:
    def test_reads_and_clears_buffer(self, runner, tmp_buffers):
        buffer_file = tmp_buffers / "my-project.md"
        buffer_file.write_text(
            "---\nfrom: my-api\ntimestamp: 2026-03-26T14:30:00\n---\nschema updated\n\n"
        )

        with (
            patch("jacobs_ladder.cli.BUFFERS_DIR", tmp_buffers),
            patch("jacobs_ladder.cli._get_current_instance_name", return_value="my-project"),
        ):
            result = runner.invoke(cli, ["pull"])

        assert result.exit_code == 0
        assert "schema updated" in result.output
        assert not buffer_file.exists()

    def test_no_messages(self, runner, tmp_buffers):
        with (
            patch("jacobs_ladder.cli.BUFFERS_DIR", tmp_buffers),
            patch("jacobs_ladder.cli._get_current_instance_name", return_value="my-project"),
        ):
            result = runner.invoke(cli, ["pull"])

        assert result.exit_code == 0
        assert "No new messages" in result.output


class TestStatus:
    def test_shows_buffer_sizes(self, runner, tmp_buffers):
        (tmp_buffers / "my-api.md").write_text("x" * 100)
        (tmp_buffers / "my-client.md").write_text("y" * 200)

        with patch("jacobs_ladder.cli.BUFFERS_DIR", tmp_buffers):
            result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "my-api" in result.output
        assert "my-client" in result.output
