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
    if len(content.splitlines()) > LARGE_MESSAGE_THRESHOLD_LINES:
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
    messages = []

    # Match each message block: opening ---, frontmatter, closing ---, optional body
    pattern = re.compile(
        r"^---\n(.*?)\n---\n?(.*?)(?=^---\n|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    for match in pattern.finditer(text):
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
