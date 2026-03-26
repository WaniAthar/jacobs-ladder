# Jacob's Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI + Claude Code skill that lets Claude instances in different projects publish and pull messages to/from each other via a local filesystem buffer.

**Architecture:** A `jacobs-ladder` CLI (built with `click`) handles process discovery (`psutil`), buffer I/O (markdown files at `~/.jacobs-ladder/buffers/`), and cleanup. A Claude Code skill (`/jacobs-ladder`) provides the conversational interface and invokes the CLI. Messages are plain markdown; large messages are stored as files in the publisher's outbox with pointers in the buffer.

**Tech Stack:** Python 3.9+, click, psutil, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `jacobs_ladder/__init__.py`
- Create: `jacobs_ladder/config.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "jacobs-ladder"
version = "0.1.0"
description = "Inter-Claude-Code instance communication via local pub/sub buffers"
requires-python = ">=3.9"
dependencies = [
    "click>=8.0",
    "psutil>=5.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-tmp-files>=0.0.2",
]

[project.scripts]
jacobs-ladder = "jacobs_ladder.cli:cli"

[tool.setuptools.packages.find]
include = ["jacobs_ladder*"]
```

- [ ] **Step 2: Create `jacobs_ladder/__init__.py`**

```python
"""Jacob's Ladder — inter-Claude-Code instance communication."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `jacobs_ladder/config.py`**

```python
"""Paths, thresholds, and constants."""

from pathlib import Path

JACOBS_LADDER_HOME = Path.home() / ".jacobs-ladder"
BUFFERS_DIR = JACOBS_LADDER_HOME / "buffers"
OUTBOX_DIR_NAME = ".jacobs-ladder/outbox"

LARGE_MESSAGE_THRESHOLD_BYTES = 50_000  # ~50KB
LARGE_MESSAGE_THRESHOLD_LINES = 500


def ensure_dirs() -> None:
    """Create global directories if they don't exist."""
    BUFFERS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Install in editable mode**

Run: `pip install -e ".[dev]"`
Expected: Successfully installed jacobs-ladder with click, psutil, pytest

- [ ] **Step 5: Verify install**

Run: `jacobs-ladder --help`
Expected: Error — cli module not yet created. This confirms the entry point is wired up (will work after Task 3).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml jacobs_ladder/__init__.py jacobs_ladder/config.py
git commit -m "feat: project scaffolding with pyproject.toml and config"
```

---

### Task 2: Process Discovery

**Files:**
- Create: `jacobs_ladder/discovery.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write failing tests for discovery**

Create `tests/test_discovery.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_discovery.py -v`
Expected: FAIL — `ImportError: cannot import name 'discover_instances' from 'jacobs_ladder.discovery'`

- [ ] **Step 3: Implement discovery module**

Create `jacobs_ladder/discovery.py`:

```python
"""Process scanning and Claude Code instance detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class Instance:
    """A discovered Claude Code instance."""

    name: str
    pid: int
    cwd: str


def _is_claude_process(proc: psutil.Process) -> bool:
    """Check if a process is a Claude Code instance."""
    try:
        cmdline = proc.cmdline()
        return any("claude" == arg for arg in cmdline)
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False


def _get_cwd(proc: psutil.Process) -> str | None:
    """Get the working directory of a process, or None if inaccessible."""
    try:
        return proc.cwd()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def _deduplicate_names(instances: list[Instance]) -> list[Instance]:
    """Append numeric suffixes to duplicate instance names."""
    seen: dict[str, int] = {}
    result: list[Instance] = []

    for inst in instances:
        base_name = inst.name
        if base_name in seen:
            seen[base_name] += 1
            inst.name = f"{base_name}-{seen[base_name]}"
        else:
            seen[base_name] = 1
        result.append(inst)

    # Rename the first occurrence if there were duplicates
    for inst in result:
        base = inst.name.split("-")[0] if "-" in inst.name else inst.name
        # Already handled by suffix logic
    return result


def discover_instances(current_cwd: str | None = None) -> list[Instance]:
    """Find all running Claude Code instances, excluding the current one.

    Args:
        current_cwd: Working directory of the calling instance. If provided,
                     processes with this cwd are excluded from results.

    Returns:
        List of discovered Instance objects.
    """
    if current_cwd is None:
        current_cwd = str(Path.cwd())

    current_cwd = str(Path(current_cwd).resolve())
    raw_instances: list[Instance] = []

    for proc in psutil.process_iter():
        if not _is_claude_process(proc):
            continue

        cwd = _get_cwd(proc)
        if cwd is None:
            continue

        resolved_cwd = str(Path(cwd).resolve())
        if resolved_cwd == current_cwd:
            continue

        name = Path(cwd).name
        raw_instances.append(Instance(name=name, pid=proc.pid, cwd=cwd))

    return _deduplicate_names(raw_instances)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_discovery.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add jacobs_ladder/discovery.py tests/test_discovery.py
git commit -m "feat: process discovery for Claude Code instances"
```

---

### Task 3: Buffer Management

**Files:**
- Create: `jacobs_ladder/buffer.py`
- Create: `tests/test_buffer.py`

- [ ] **Step 1: Write failing tests for buffer operations**

Create `tests/test_buffer.py`:

```python
"""Tests for buffer read/write/cleanup."""

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

from jacobs_ladder.buffer import (
    write_to_buffer,
    read_buffer,
    clear_buffer,
    is_large_message,
    write_large_message,
    Message,
)
from jacobs_ladder.config import LARGE_MESSAGE_THRESHOLD_BYTES


class TestIsLargeMessage:
    def test_small_message(self):
        assert is_large_message("short message") is False

    def test_large_message_by_bytes(self):
        content = "x" * (LARGE_MESSAGE_THRESHOLD_BYTES + 1)
        assert is_large_message(content) is True

    def test_large_message_by_lines(self):
        content = "\n".join(["line"] * 501)
        assert is_large_message(content) is True


class TestWriteToBuffer:
    def test_writes_message_with_frontmatter(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        write_to_buffer(
            target="my-client",
            sender="my-api",
            content="## Schema changed\n\nNew field added.",
            buffers_dir=buffers_dir,
        )

        buffer_file = buffers_dir / "my-client.md"
        assert buffer_file.exists()
        text = buffer_file.read_text()
        assert "from: my-api" in text
        assert "## Schema changed" in text
        assert "New field added." in text

    def test_appends_multiple_messages(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        write_to_buffer(
            target="my-client",
            sender="my-api",
            content="First message",
            buffers_dir=buffers_dir,
        )
        write_to_buffer(
            target="my-client",
            sender="my-api",
            content="Second message",
            buffers_dir=buffers_dir,
        )

        text = (buffers_dir / "my-client.md").read_text()
        assert "First message" in text
        assert "Second message" in text


class TestWriteLargeMessage:
    def test_creates_outbox_file_and_pointer(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()
        project_dir = tmp_path / "my-api"
        project_dir.mkdir()

        large_content = "x" * (LARGE_MESSAGE_THRESHOLD_BYTES + 1)

        write_large_message(
            target="my-client",
            sender="my-api",
            content=large_content,
            sender_project_dir=str(project_dir),
            buffers_dir=buffers_dir,
        )

        # Buffer should contain a file-reference pointer
        buffer_text = (buffers_dir / "my-client.md").read_text()
        assert "type: file-reference" in buffer_text

        # Outbox file should exist in the sender's project
        outbox_dir = project_dir / ".jacobs-ladder" / "outbox"
        assert outbox_dir.exists()
        outbox_files = list(outbox_dir.glob("*.md"))
        assert len(outbox_files) == 1
        assert outbox_files[0].read_text() == large_content


class TestReadBuffer:
    def test_reads_inline_messages(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()
        buffer_file = buffers_dir / "my-client.md"
        buffer_file.write_text(dedent("""\
            ---
            from: my-api
            timestamp: 2026-03-26T14:30:00
            ---
            ## Schema changed

            New field added.
        """))

        messages = read_buffer(instance="my-client", buffers_dir=buffers_dir)

        assert len(messages) == 1
        assert messages[0].sender == "my-api"
        assert "Schema changed" in messages[0].content

    def test_reads_file_reference_messages(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        # Create the referenced file
        ref_file = tmp_path / "outbox" / "msg.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("Large content here")

        buffer_file = buffers_dir / "my-client.md"
        buffer_file.write_text(dedent(f"""\
            ---
            from: my-api
            timestamp: 2026-03-26T14:30:00
            type: file-reference
            path: {ref_file}
            ---
        """))

        messages = read_buffer(instance="my-client", buffers_dir=buffers_dir)

        assert len(messages) == 1
        assert messages[0].content == "Large content here"

    def test_returns_empty_when_no_buffer(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        messages = read_buffer(instance="my-client", buffers_dir=buffers_dir)

        assert messages == []


class TestClearBuffer:
    def test_deletes_buffer_file(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()
        buffer_file = buffers_dir / "my-client.md"
        buffer_file.write_text("some content")

        clear_buffer(instance="my-client", buffers_dir=buffers_dir)

        assert not buffer_file.exists()

    def test_deletes_referenced_outbox_files(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        ref_file = tmp_path / "outbox" / "msg.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("Large content")

        buffer_file = buffers_dir / "my-client.md"
        buffer_file.write_text(dedent(f"""\
            ---
            from: my-api
            timestamp: 2026-03-26T14:30:00
            type: file-reference
            path: {ref_file}
            ---
        """))

        clear_buffer(instance="my-client", buffers_dir=buffers_dir)

        assert not buffer_file.exists()
        assert not ref_file.exists()

    def test_noop_when_no_buffer(self, tmp_path):
        buffers_dir = tmp_path / "buffers"
        buffers_dir.mkdir()

        # Should not raise
        clear_buffer(instance="my-client", buffers_dir=buffers_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_buffer.py -v`
Expected: FAIL — `ImportError: cannot import name 'write_to_buffer' from 'jacobs_ladder.buffer'`

- [ ] **Step 3: Implement buffer module**

Create `jacobs_ladder/buffer.py`:

```python
"""Buffer read/write/cleanup logic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jacobs_ladder.config import (
    BUFFERS_DIR,
    LARGE_MESSAGE_THRESHOLD_BYTES,
    LARGE_MESSAGE_THRESHOLD_LINES,
    OUTBOX_DIR_NAME,
)


@dataclass
class Message:
    """A message read from a buffer."""

    sender: str
    timestamp: str
    content: str


def is_large_message(content: str) -> bool:
    """Check if a message exceeds the size threshold."""
    if len(content.encode("utf-8")) > LARGE_MESSAGE_THRESHOLD_BYTES:
        return True
    if content.count("\n") > LARGE_MESSAGE_THRESHOLD_LINES:
        return True
    return False


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def write_to_buffer(
    target: str,
    sender: str,
    content: str,
    buffers_dir: Path = BUFFERS_DIR,
) -> None:
    """Write an inline message to a target instance's buffer.

    Messages are appended, so multiple publishes accumulate.
    """
    buffers_dir.mkdir(parents=True, exist_ok=True)
    buffer_file = buffers_dir / f"{target}.md"

    entry = f"---\nfrom: {sender}\ntimestamp: {_timestamp()}\n---\n{content}\n\n"

    with buffer_file.open("a") as f:
        f.write(entry)


def write_large_message(
    target: str,
    sender: str,
    content: str,
    sender_project_dir: str,
    buffers_dir: Path = BUFFERS_DIR,
) -> Path:
    """Write a large message to the sender's outbox and a pointer to the buffer.

    Returns the path to the outbox file.
    """
    outbox_dir = Path(sender_project_dir) / OUTBOX_DIR_NAME
    outbox_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    outbox_file = outbox_dir / f"{ts}.md"
    outbox_file.write_text(content)

    buffers_dir.mkdir(parents=True, exist_ok=True)
    buffer_file = buffers_dir / f"{target}.md"

    pointer = (
        f"---\nfrom: {sender}\ntimestamp: {_timestamp()}\n"
        f"type: file-reference\npath: {outbox_file}\n---\n\n"
    )

    with buffer_file.open("a") as f:
        f.write(pointer)

    return outbox_file


def _parse_messages(text: str) -> list[dict]:
    """Parse a buffer file into raw message dicts (frontmatter + body)."""
    blocks = re.split(r"(?=^---\n)", text, flags=re.MULTILINE)
    messages = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        match = re.match(
            r"^---\n(.*?)\n---\n?(.*)",
            block,
            flags=re.DOTALL,
        )
        if not match:
            continue

        frontmatter_text = match.group(1)
        body = match.group(2).strip()

        frontmatter: dict[str, str] = {}
        for line in frontmatter_text.strip().splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                frontmatter[key.strip()] = value.strip()

        frontmatter["_body"] = body
        messages.append(frontmatter)

    return messages


def read_buffer(
    instance: str,
    buffers_dir: Path = BUFFERS_DIR,
) -> list[Message]:
    """Read all messages from an instance's buffer.

    For file-reference messages, reads the referenced file's content.
    """
    buffer_file = buffers_dir / f"{instance}.md"
    if not buffer_file.exists():
        return []

    text = buffer_file.read_text()
    if not text.strip():
        return []

    raw_messages = _parse_messages(text)
    result: list[Message] = []

    for msg in raw_messages:
        sender = msg.get("from", "unknown")
        timestamp = msg.get("timestamp", "")

        if msg.get("type") == "file-reference":
            ref_path = Path(msg.get("path", ""))
            if ref_path.exists():
                content = ref_path.read_text()
            else:
                content = f"[Referenced file not found: {ref_path}]"
        else:
            content = msg.get("_body", "")

        result.append(Message(sender=sender, timestamp=timestamp, content=content))

    return result


def clear_buffer(
    instance: str,
    buffers_dir: Path = BUFFERS_DIR,
) -> None:
    """Clear an instance's buffer and delete any referenced outbox files."""
    buffer_file = buffers_dir / f"{instance}.md"
    if not buffer_file.exists():
        return

    # Parse to find file-references to clean up
    text = buffer_file.read_text()
    raw_messages = _parse_messages(text)

    for msg in raw_messages:
        if msg.get("type") == "file-reference":
            ref_path = Path(msg.get("path", ""))
            if ref_path.exists():
                ref_path.unlink()

    buffer_file.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_buffer.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add jacobs_ladder/buffer.py tests/test_buffer.py
git commit -m "feat: buffer read/write/cleanup for message passing"
```

---

### Task 4: CLI Interface

**Files:**
- Create: `jacobs_ladder/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI commands**

Create `tests/test_cli.py`:

```python
"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import patch, MagicMock

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


import pytest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'cli' from 'jacobs_ladder.cli'`

- [ ] **Step 3: Implement CLI module**

Create `jacobs_ladder/cli.py`:

```python
"""CLI entry point for Jacob's Ladder."""

from __future__ import annotations

from pathlib import Path

import click

from jacobs_ladder.buffer import (
    clear_buffer,
    is_large_message,
    read_buffer,
    write_large_message,
    write_to_buffer,
)
from jacobs_ladder.config import BUFFERS_DIR, ensure_dirs
from jacobs_ladder.discovery import discover_instances


def _get_current_instance_name() -> str:
    """Derive instance name from current working directory."""
    return Path.cwd().name


@click.group()
def cli() -> None:
    """Jacob's Ladder — inter-Claude-Code instance communication."""
    ensure_dirs()


@cli.command()
def discover() -> None:
    """List active Claude Code instances."""
    instances = discover_instances()

    if not instances:
        click.echo("No other Claude agents running at the moment.")
        return

    click.echo("Active instances:")
    for inst in instances:
        click.echo(f"  - {inst.name} (pid {inst.pid}) — {inst.cwd}")


@cli.command()
@click.option("--to", "target", required=False, help="Target instance name.")
@click.option("--message", required=False, help="Message content (inline).")
@click.option("--file", "file_path", required=False, type=click.Path(exists=True), help="File to publish.")
@click.option("--broadcast", is_flag=True, help="Publish to all active instances.")
def publish(target: str | None, message: str | None, file_path: str | None, broadcast: bool) -> None:
    """Publish a message to another instance's buffer."""
    instances = discover_instances()
    sender = _get_current_instance_name()

    if broadcast:
        targets = [inst.name for inst in instances]
        if not targets:
            click.echo("No other Claude agents running at the moment.")
            return
    elif target:
        matching = [inst for inst in instances if inst.name == target]
        if not matching:
            click.echo(f"Instance '{target}' is not running.")
            return
        targets = [target]
    else:
        click.echo("Error: provide --to <instance> or --broadcast.")
        return

    if file_path:
        content = Path(file_path).read_text()
    elif message:
        content = message
    else:
        click.echo("Error: provide --message or --file.")
        return

    for t in targets:
        if is_large_message(content):
            write_large_message(
                target=t,
                sender=sender,
                content=content,
                sender_project_dir=str(Path.cwd()),
                buffers_dir=BUFFERS_DIR,
            )
        else:
            write_to_buffer(
                target=t,
                sender=sender,
                content=content,
                buffers_dir=BUFFERS_DIR,
            )

    names = ", ".join(targets)
    click.echo(f"Published to: {names}")


@cli.command()
def pull() -> None:
    """Read and clear incoming messages."""
    instance = _get_current_instance_name()
    messages = read_buffer(instance=instance, buffers_dir=BUFFERS_DIR)

    if not messages:
        click.echo("No new messages.")
        return

    for msg in messages:
        click.echo(f"\n--- From: {msg.sender} ({msg.timestamp}) ---")
        click.echo(msg.content)

    clear_buffer(instance=instance, buffers_dir=BUFFERS_DIR)
    click.echo(f"\n({len(messages)} message(s) cleared)")


@cli.command()
def status() -> None:
    """Show buffer sizes for all instances."""
    if not BUFFERS_DIR.exists():
        click.echo("No buffers found.")
        return

    buffer_files = sorted(BUFFERS_DIR.glob("*.md"))
    if not buffer_files:
        click.echo("No buffers found.")
        return

    click.echo("Buffer status:")
    for bf in buffer_files:
        name = bf.stem
        size = bf.stat().st_size
        click.echo(f"  - {name}: {size} bytes")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Verify CLI works end-to-end**

Run: `jacobs-ladder --help`
Expected: Shows help with discover, publish, pull, status commands.

Run: `jacobs-ladder discover`
Expected: Lists any running Claude instances (or "No other Claude agents running").

- [ ] **Step 6: Commit**

```bash
git add jacobs_ladder/cli.py tests/test_cli.py
git commit -m "feat: CLI interface with discover, publish, pull, status commands"
```

---

### Task 5: Claude Code Skill

**Files:**
- Create: `skill/jacobs-ladder.md`

- [ ] **Step 1: Create the skill file**

Create `skill/jacobs-ladder.md`:

````markdown
---
name: jacobs-ladder
description: Communicate with other Claude Code instances running on the same machine. Publish changes (API schemas, configs, structural updates) to other instances and pull incoming messages. Use when the user mentions other Claude instances, wants to share changes across projects, or says "publish", "pull", "broadcast", or "check for updates".
---

# Jacob's Ladder

You are communicating with other Claude Code instances via the `jacobs-ladder` CLI tool.

## Commands

All commands are run via the Bash tool:

- `jacobs-ladder discover` — list other running Claude Code instances
- `jacobs-ladder publish --to <name> --message "<content>"` — send an inline message
- `jacobs-ladder publish --to <name> --file <path>` — send a file's content
- `jacobs-ladder publish --broadcast --message "<content>"` — send to all instances
- `jacobs-ladder pull` — read and clear your incoming message buffer
- `jacobs-ladder status` — check buffer sizes

## Behavior

### When the user asks to publish:
1. Run `jacobs-ladder discover` to see active instances
2. If the user hasn't specified a target, show the list and ask which instance to publish to
3. Determine what content to publish — the user may ask you to publish specific content, a file, or to summarize recent changes
4. For inline content, use `--message`. For file content, use `--file`
5. Confirm what was published and to whom

### When the user asks to pull / check for updates:
1. Run `jacobs-ladder pull`
2. Present the messages clearly to the user
3. Analyze the messages and proactively suggest what needs updating in the current project based on the incoming changes
4. Offer to make the necessary updates

### When the user asks to discover / list instances:
1. Run `jacobs-ladder discover`
2. Present the list of active instances

### Default action (just `/jacobs-ladder` with no arguments):
1. Run `jacobs-ladder discover` to show active instances
2. Run `jacobs-ladder pull` to check for messages
3. Present both results

## Message Content Guidelines

When the user asks you to publish something, package it as clear markdown:
- API changes: include endpoint, method, request/response schemas
- Config changes: include the changed keys and new values
- Structural changes: include file paths and what moved/changed
- Schema changes: include the full updated schema or a clear diff

Always include enough context that the receiving Claude instance can understand and act on the change without asking follow-up questions.
````

- [ ] **Step 2: Commit**

```bash
git add skill/jacobs-ladder.md
git commit -m "feat: Claude Code skill for /jacobs-ladder interface"
```

---

### Task 6: Installation & CLAUDE.md

**Files:**
- Create: `CLAUDE.md`
- Create: `README.md`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Jacob's Ladder is a Python CLI + Claude Code skill for pub/sub communication between Claude Code instances on the same machine. One instance publishes changes (API schemas, configs, etc.) to another instance's buffer; the receiver pulls and auto-clears.

## Build & Install

```bash
pip install -e ".[dev]"    # editable install with dev deps
```

## Tests

```bash
pytest                           # all tests
pytest tests/test_discovery.py   # just discovery
pytest tests/test_buffer.py      # just buffer
pytest tests/test_cli.py         # just CLI
pytest -k "test_name" -v         # single test
```

## Architecture

- `jacobs_ladder/config.py` — paths and thresholds (`~/.jacobs-ladder/buffers/`, 50KB large message threshold)
- `jacobs_ladder/discovery.py` — scans running processes with `psutil` to find Claude Code instances, deduplicates names
- `jacobs_ladder/buffer.py` — writes/reads/clears markdown message buffers; large messages go to sender's `.jacobs-ladder/outbox/` with a pointer in the buffer
- `jacobs_ladder/cli.py` — `click` CLI with `discover`, `publish`, `pull`, `status` commands
- `skill/jacobs-ladder.md` — Claude Code skill file teaching Claude how to use the CLI

## Key Design Decisions

- Messages are plain markdown with YAML frontmatter (from, timestamp, type)
- Small messages go inline in `~/.jacobs-ladder/buffers/<target>.md`; large ones are stored as files in the publisher's `.jacobs-ladder/outbox/` with a file-reference pointer in the buffer
- Pulling auto-clears the buffer and deletes referenced outbox files
- Publishing requires the target instance to be running (no offline buffering)
- Instance identity is derived from the working directory name of the `claude` process

## Skill Installation

Copy `skill/jacobs-ladder.md` to `~/.claude/skills/` (or the appropriate skill directory) for global access across all projects.
```

- [ ] **Step 2: Create README.md**

```markdown
# Jacob's Ladder

Communication bridge between Claude Code instances running on the same machine.

When you have Claude Code running in multiple projects that depend on each other (e.g., API server + client), Jacob's Ladder lets one instance publish changes and another pull them — no more manually copying docs between terminals.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

### Discover other instances
```bash
jacobs-ladder discover
```

### Publish a message
```bash
jacobs-ladder publish --to my-client --message "## API Change\n\nThe /users endpoint now returns..."
jacobs-ladder publish --to my-client --file docs/api-schema.md
jacobs-ladder publish --broadcast --message "Breaking change: auth header format changed"
```

### Pull incoming messages
```bash
jacobs-ladder pull
```

### Check buffer status
```bash
jacobs-ladder status
```

## Claude Code Skill

Copy `skill/jacobs-ladder.md` to your Claude Code skills directory for natural language access:

- "publish this schema change to my-client"
- "check for updates from other projects"
- `/jacobs-ladder` to discover + pull in one go
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add CLAUDE.md and README.md"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass (discovery: 6, buffer: 10, CLI: 6 = 22 tests)

- [ ] **Step 2: Verify CLI commands work**

Run: `jacobs-ladder discover`
Expected: Lists running Claude instances or "No other Claude agents running"

Run: `jacobs-ladder status`
Expected: "No buffers found." (clean state)

- [ ] **Step 3: Commit any fixes**

If any tests or commands needed fixes, commit them:

```bash
git add -A
git commit -m "fix: address issues found during e2e verification"
```
