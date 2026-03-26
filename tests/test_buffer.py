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
