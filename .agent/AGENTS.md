# Superpowers for Antigravity

You have superpowers.

This profile adapts Superpowers workflows for Antigravity with strict single-flow execution.

## Core Rules

1. Prefer local skills in `.agent/skills/<skill-name>/SKILL.md`.
2. Execute one core task at a time with `task_boundary`.
3. Use `browser_subagent` only for browser automation tasks.
4. Track checklist progress in `<project-root>/docs/plans/task.md` (table-only live tracker).
5. Keep changes scoped to the requested task and verify before completion claims.

## Tool Translation Contract

When source skills reference legacy tool names, use these Antigravity equivalents:

- Legacy assistant/platform names -> `Antigravity`
- `Task` tool -> `browser_subagent` for browser tasks, otherwise sequential `task_boundary`
- `Skill` tool -> `view_file ~/.gemini/skills/<skill-name>/SKILL.md` (or project-local `.agent/skills/<skill-name>/SKILL.md`)
- `TodoWrite` -> update `<project-root>/docs/plans/task.md` task list
- File operations -> `view_file`, `write_to_file`, `replace_file_content`, `multi_replace_file_content`
- Directory listing -> `list_dir`
- Code structure -> `view_file_outline`, `view_code_item`
- Search -> `grep_search`, `find_by_name`
- Shell -> `run_command`
- Web fetch -> `read_url_content`
- Web search -> `search_web`
- Image generation -> `generate_image`
- User communication during tasks -> `notify_user`
- MCP tools -> `mcp_*` tool family

## Skill Loading

- First preference: project skills at `.agent/skills`.
- Second preference: user skills at `~/.gemini/skills`.
- If both exist, project-local skills win for this profile.
- Optional parity assets may exist at `.agent/workflows/*` and `.agent/agents/*` as entrypoint shims/reference profiles.
- These assets do not change the strict single-flow execution requirements in this file.

## Single-Flow Execution Model

- Do not dispatch multiple coding agents in parallel.
- Decompose large work into ordered, explicit steps.
- Keep exactly one active task at a time in `<project-root>/docs/plans/task.md`.
- If browser work is required, isolate it in a dedicated browser step.

## Verification Discipline

Before saying a task is done:

1. Run the relevant verification command(s).
2. Confirm exit status and key output.
3. Update `<project-root>/docs/plans/task.md`.
4. Report evidence, then claim completion.

<!-- agent-env:start -->
## Operating Contract

### Development Principles
- Prefer small, focused changes. Inspect before modifying.
- Plan non-trivial work. Test changes. Verify before claiming completion.
- Do not hide failures. Do not invent test results.
- Never claim a command succeeded unless it was actually executed.

### Guardrails (always apply)
Read and obey `.agent/guardrails/`: security, git, filesystem, docker, production.
When a request conflicts with a guardrail, refuse that approach, explain briefly,
and offer a safe alternative.

### Skills & Workflows
- Skills: `.agent/skills/` (Superpowers + docker, python, linux, aws, debugging, embedded).
- Workflows: `.agent/workflows/` (feature, bugfix, docker, release).
- Use the `security-reviewer` agent for changes touching auth, secrets, shell,
  Docker, cloud, or dependencies. It must inspect the real diff.

### Definition of Done
A task is NOT complete until:
- [ ] Requested behavior implemented
- [ ] Relevant tests pass
- [ ] Relevant lint/type checks pass
- [ ] No unintended files changed
- [ ] Git diff inspected
- [ ] No secrets exposed
- [ ] Runtime behavior verified (real output shown)
- [ ] Documentation updated when necessary
<!-- agent-env:end -->
