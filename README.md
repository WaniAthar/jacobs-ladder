# Jacob's Ladder

> **Getting started:** Copy the install commands below into Claude Code, or paste this repo URL and let the agent guide you.

```
/plugin marketplace add WaniAthar/jacobs-ladder
/plugin install jacobs-ladder@jacobs-ladder
/reload-plugins
```

A pub/sub communication bridge between Claude Code instances running on the same machine. When you have Claude Code running in multiple projects that depend on each other (e.g., API server + client), Jacob's Ladder lets one instance publish changes and another pull them — no more manually copying context between terminals.

- Automatic discovery of running Claude Code instances
- Publish markdown messages to a specific instance or broadcast to all
- Pull and auto-clear incoming messages
- Large message support via file references
- Natural language access via `/jacobs-ladder`

---

## Agent Install Guide

The instructions below are for you, the Claude Code agent. Follow them step by step to install Jacob's Ladder for the user.

### Step 1: Install the CLI

The `jacobs-ladder` CLI needs to be on the user's system. It requires Python 3.9+.

First, check what's available:

```bash
command -v uv && echo "uv found" || echo "uv not found"
command -v pip && echo "pip found" || echo "pip not found"
```

Then clone the repo and install:

```bash
git clone https://github.com/WaniAthar/jacobs-ladder.git /tmp/jacobs-ladder
cd /tmp/jacobs-ladder
```

If uv is available (preferred):

```bash
uv tool install -e .
```

If only pip is available:

```bash
pip install -e .
```

Verify the CLI is on PATH:

```bash
jacobs-ladder --help
```

If the command is not found, let the user know and help troubleshoot their PATH.

### Step 2: Install the plugin

Tell the user to run these commands in Claude Code, one at a time:

```
/plugin marketplace add WaniAthar/jacobs-ladder
```

```
/plugin install jacobs-ladder@jacobs-ladder
```

```
/reload-plugins
```

This adds the repo as a marketplace, installs the plugin from it, and reloads so the `/jacobs-ladder` skill becomes available.

### Step 3: Verify

Run a quick check to confirm the CLI is working:

```bash
jacobs-ladder discover
```

This should return a list of active Claude Code instances (or an empty list if only one is running). If it errors, the CLI install failed — go back to step 1.

Then tell the user to try `/jacobs-ladder` to confirm the skill is loaded.

Let the user know installation is complete.

---

## Usage

### CLI commands

```bash
jacobs-ladder discover                                    # list running instances
jacobs-ladder publish --to <name> --message "..."         # send to one instance
jacobs-ladder publish --to <name> --file <path>           # send a file
jacobs-ladder publish --broadcast --message "..."         # send to all
jacobs-ladder pull                                        # read & clear incoming
jacobs-ladder status                                      # check buffer sizes
```

### Skill

The `/jacobs-ladder` skill handles all of this through natural language. See `skills/jacobs-ladder/SKILL.md` for the full behavior spec.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
