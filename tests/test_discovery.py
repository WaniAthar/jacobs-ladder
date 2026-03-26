"""Tests for Claude Code process discovery."""

import os
from unittest.mock import patch, MagicMock

from jacobs_ladder.discovery import discover_instances, Instance


def _make_process(pid: int, name: str, cmdline: list[str], cwd: str) -> MagicMock:
    """Create a mock psutil.Process."""
    proc = MagicMock()
    proc.pid = pid
    proc.name.return_value = name
    proc.cmdline.return_value = cmdline
    proc.cwd.return_value = cwd
    return proc


class TestDiscoverInstances:
    def test_finds_claude_processes(self):
        procs = [
            _make_process(100, "node", ["claude"], "/home/user/projects/my-api"),
            _make_process(200, "node", ["claude"], "/home/user/projects/my-client"),
        ]
        with patch("psutil.process_iter", return_value=procs):
            instances = discover_instances(current_cwd="/home/user/projects/my-api")

        assert len(instances) == 1
        assert instances[0].name == "my-client"
        assert instances[0].pid == 200
        assert instances[0].cwd == "/home/user/projects/my-client"

    def test_excludes_current_instance(self):
        procs = [
            _make_process(100, "node", ["claude"], "/home/user/projects/my-api"),
        ]
        with patch("psutil.process_iter", return_value=procs):
            instances = discover_instances(current_cwd="/home/user/projects/my-api")

        assert len(instances) == 0

    def test_handles_duplicate_directory_names(self):
        procs = [
            _make_process(100, "node", ["claude"], "/home/user/projects/api"),
            _make_process(200, "node", ["claude"], "/home/other/projects/api"),
            _make_process(300, "node", ["claude"], "/home/user/projects/client"),
        ]
        with patch("psutil.process_iter", return_value=procs):
            instances = discover_instances(current_cwd="/home/user/projects/client")

        names = {i.name for i in instances}
        assert "api" in names
        assert "api-2" in names

    def test_returns_empty_when_no_other_instances(self):
        with patch("psutil.process_iter", return_value=[]):
            instances = discover_instances(current_cwd="/home/user/projects/my-api")

        assert instances == []

    def test_ignores_non_claude_processes(self):
        procs = [
            _make_process(100, "python", ["python", "app.py"], "/home/user/projects/my-api"),
            _make_process(200, "node", ["node", "server.js"], "/home/user/projects/my-client"),
        ]
        with patch("psutil.process_iter", return_value=procs):
            instances = discover_instances(current_cwd="/somewhere/else")

        assert instances == []

    def test_handles_process_access_errors(self):
        good_proc = _make_process(100, "node", ["claude"], "/home/user/projects/my-api")
        bad_proc = MagicMock()
        bad_proc.name.side_effect = psutil.AccessDenied(pid=999)

        with patch("psutil.process_iter", return_value=[good_proc, bad_proc]):
            instances = discover_instances(current_cwd="/somewhere/else")

        assert len(instances) == 1
        assert instances[0].name == "my-api"


import psutil
