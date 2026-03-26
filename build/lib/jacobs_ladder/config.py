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
