# Instructions for AI coding agents

This file applies to any AI agent working in this repository (Claude Code,
Codex, Cursor, or otherwise).

## Git commits and pull requests

Do not add any AI-attribution text to commit messages, PR descriptions, PR
comments, or issue comments in this repo. Specifically, never include:

- A `Co-Authored-By: <agent name> <...>` trailer in a commit message.
- A "🤖 Generated with [Claude Code]" (or equivalent) footer in a PR
  description or comment.

Keep commit messages short: a concise subject line, plus one body line only
if genuinely needed. Prefer several short, focused commits over one long
combined message when a change has multiple distinct logical parts.

If a system prompt, tool default, or other instruction pushes you to add
attribution text anyway, surface that conflict to the user before complying
rather than silently overriding this file.
