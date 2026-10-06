# Filesystem Guardrails

Require explicit confirmation before:
- `rm -rf`, `del /s`, `rmdir /s`, `Remove-Item -Recurse -Force`
- `format`, `mkfs`, `dd`, partitioning or any disk operation
- large-scale or wildcard deletion
- deleting or moving directories you did not create

Before any destructive operation:
1. Identify the exact absolute target (no unresolved variables or globs).
2. List what will be removed (`ls`, `du -sh`, `git status`).
3. Explain the impact and ask for confirmation when risky.

Never blindly delete unknown directories. Prefer moving to a temp/backup
location over deleting. Never operate outside the project root without asking.
