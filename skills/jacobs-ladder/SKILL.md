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
