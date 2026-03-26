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
- `skills/jacobs-ladder/SKILL.md` — Claude Code skill file teaching Claude how to use the CLI

## Key Design Decisions

- Messages are plain markdown with YAML frontmatter (from, timestamp, type)
- Small messages go inline in `~/.jacobs-ladder/buffers/<target>.md`; large ones are stored as files in the publisher's `.jacobs-ladder/outbox/` with a file-reference pointer in the buffer
- Pulling auto-clears the buffer and deletes referenced outbox files
- Publishing requires the target instance to be running (no offline buffering)
- Instance identity is derived from the working directory name of the `claude` process

## Plugin Installation

```
/plugin marketplace add WaniAthar/jacobs-ladder
/plugin install jacobs-ladder@jacobs-ladder
/reload-plugins
```
