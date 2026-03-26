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
