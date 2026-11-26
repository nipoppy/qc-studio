# Instructions for AI coding agents

This file applies to any AI agent working in this repository — Claude Code,
Codex, Cursor, or otherwise.

## Read these before doing related work

QC-Studio keeps its detailed, project-specific agent guidance as markdown
under `.claude/skills/`. Claude Code loads these automatically by name; other
tools don't know they exist, so read the relevant one yourself before the
matching task:

| File | Read it before... |
|---|---|
| [`.claude/skills/qcs-reviewing-code/SKILL.md`](.claude/skills/qcs-reviewing-code/SKILL.md) | Reviewing a diff, PR, commit, or file for defects. |
| [`.claude/skills/qcs-generating-tests/SKILL.md`](.claude/skills/qcs-generating-tests/SKILL.md) | Writing or updating pytest tests in `ui/tests/`. |
| [`.claude/skills/qcs-understanding-e2e/SKILL.md`](.claude/skills/qcs-understanding-e2e/SKILL.md) | Touching anything under `e2e/`, or before writing an e2e test. |
| [`.claude/skills/qcs-playwright-testing/SKILL.md`](.claude/skills/qcs-playwright-testing/SKILL.md) | Writing a specific Playwright test in `e2e/tests/`. |

Each file states up front when it applies. If a task in this repo matches
that description, open the file first rather than guessing at conventions —
they encode real project decisions (why fixtures are scoped the way they
are, which naming patterns are stale, what counts as a real bug versus a
style preference) that aren't obvious from the code alone.

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
