# Git Guardrails

NEVER run automatically (ask first, explain impact):
- `git push --force` / `--force-with-lease`
- `git reset --hard`
- `git clean -fd`
- deleting `main` / `master`
- deleting branches that contain unmerged work
- rewriting already-published history (rebase/amend of pushed commits)

Before every commit:
1. `git status`
2. `git diff` (and `git diff --staged`)
3. Run the relevant tests
4. Scan the diff for secrets
5. Confirm ONLY intended files changed

"Clean up / reset everything" is not permission to be destructive: inspect
state first, show what would be lost, and ask for confirmation.
