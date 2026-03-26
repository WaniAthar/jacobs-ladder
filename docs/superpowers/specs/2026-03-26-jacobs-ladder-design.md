# Jacob's Ladder — Design Spec

A pub/sub communication system between Claude Code instances running on the same machine. Enables projects that depend on each other (e.g., client/server) to share changes without manual copy-pasting of docs and paths.

## Problem

When two Claude Code instances work on interdependent projects (e.g., API server and its client), changes in one project that affect the other require manual intervention: creating a doc, copying the path, pasting it in the other instance, and asking it to read and update. This is tedious and error-prone.

## Solution

A Python CLI tool (`jacobs-ladder`) paired with a Claude Code skill (`/jacobs-ladder`) that provides:

- **Process discovery** — automatically detect running Claude Code instances
- **Publishing** — send markdown messages to another instance's buffer
- **Pulling** — consume incoming messages and auto-clear the buffer
- **Broadcasting** — publish to all active instances at once

## Core Concepts

- **Instance** — a running Claude Code process, auto-identified by its working directory name (e.g., `/Users/cravv/Projects/my-api` -> `my-api`)
- **Buffer** — a per-instance markdown file at `~/.jacobs-ladder/buffers/<instance-name>.md`. Small messages are inline; large messages are saved as `.md` files in the publisher's project and referenced by path.
- **Publish** — write a message to another active instance's buffer
- **Pull** — read your buffer, consume the contents, signal cleanup
- **Discover** — scan running processes to find active Claude Code instances

## Constraints

- Publishing only works when the target instance is running (no offline buffering)
- Pulling auto-clears the buffer
- Same-machine only (uses local filesystem)

## Process Discovery

The CLI:

1. Scans running processes for `claude` commands using `psutil`
2. Extracts the working directory of each Claude process
3. Derives an instance name from the directory name (last path segment)
4. Returns a list:
   ```
   Active instances:
   - my-api (pid 1234) — /Users/cravv/Projects/my-api
   - my-client (pid 5678) — /Users/cravv/Projects/my-client
   ```

**Edge cases:**
- Duplicate directory names: append numeric suffix (`api`, `api-2`)
- Current instance excluded from discovery results
- No other instances: returns "No other Claude agents running at the moment"

## Publishing Flow

When publishing a message to a target instance:

1. **Discover** — verify the target is a running instance. If not, inform the user.
2. **Size check** — determine if message is small or large (threshold: ~50KB or ~500 lines)
3. **Small message** — write markdown directly into `~/.jacobs-ladder/buffers/<target>.md`:
   ```markdown
   ---
   from: my-api
   timestamp: 2026-03-26T14:30:00
   ---
   ## Updated User API Response Schema

   The `/users/:id` endpoint now returns...
   ```
4. **Large message** — save content as `.md` in publisher's project at `<project>/.jacobs-ladder/outbox/<timestamp>-<topic>.md` and write a pointer into the buffer:
   ```markdown
   ---
   from: my-api
   timestamp: 2026-03-26T14:30:00
   type: file-reference
   ---
   Large message saved at: /Users/cravv/Projects/my-api/.jacobs-ladder/outbox/2026-03-26-user-schema.md
   ```
5. **Multiple messages** — accumulate in the buffer (appended, not overwritten)
6. **Broadcast** — write to every active instance's buffer

## Pull & Cleanup Flow

When pulling messages:

1. Read `~/.jacobs-ladder/buffers/<my-instance>.md`
2. If empty: "No new messages"
3. If has messages: return all to Claude for presentation
4. If file-references exist: read the referenced `.md` files and return that content too
5. Auto-clear: delete buffer file and referenced outbox `.md` files
6. Claude presents the messages and can proactively suggest updates needed in the current project

## Skill Interface

**Slash commands:**
- `/jacobs-ladder` — discover active instances (default)
- `/jacobs-ladder publish <target>` — publish to a specific instance
- `/jacobs-ladder pull` — check for and consume incoming messages
- `/jacobs-ladder broadcast` — publish to all active instances

**Natural language:**
- "publish this schema change to my-client"
- "check for updates from other projects"
- "send the websocket event docs to all instances"
- "what other Claude instances are running?"

**CLI commands (used by skill under the hood):**
- `jacobs-ladder discover` — list active Claude instances
- `jacobs-ladder publish --to <instance> --message <content>` — write to buffer
- `jacobs-ladder publish --to <instance> --file <path>` — write file reference
- `jacobs-ladder publish --broadcast --message <content>` — write to all
- `jacobs-ladder pull` — read and clear own buffer (instance auto-detected from cwd)
- `jacobs-ladder status` — show buffer sizes for all instances

## Project Structure

```
jacobs_ladder/
├── jacobs_ladder/            # Python package
│   ├── __init__.py
│   ├── cli.py                # CLI entry point (click)
│   ├── discovery.py          # Process scanning, instance detection
│   ├── buffer.py             # Buffer read/write/cleanup logic
│   └── config.py             # Paths, thresholds, constants
├── skill/
│   └── jacobs-ladder.md      # Claude Code skill file
├── pyproject.toml            # Package config
├── tests/
│   ├── test_discovery.py
│   ├── test_buffer.py
│   └── test_cli.py
└── README.md
```

## Tech Stack

- **Python 3.9+** — broad compatibility
- **`psutil`** — cross-platform process discovery (only external dependency)
- **`click`** — CLI framework
- **Plain filesystem** — no database, buffers are markdown files
- **`pyproject.toml`** — modern packaging, installable via `pip install -e .` or `pip install .`

## Global Paths

- `~/.jacobs-ladder/buffers/` — message buffers per instance
- `<project>/.jacobs-ladder/outbox/` — large message files in publisher's project
