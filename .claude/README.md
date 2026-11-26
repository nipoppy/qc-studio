# Claude Code project config

- `agents/` and `skills/` here are shared QC-Studio conventions (code review,
  test generation, e2e testing). They're committed so anyone using Claude Code
  on this repo gets the same behavior.
- `settings.local.json` is **not** committed. It holds one person's local
  permission allowlist (which Bash commands Claude may run without asking) and
  is specific to their machine and workflow, not a project convention. If you
  want project-wide default permissions, put them in a committed
  `settings.json` instead.
