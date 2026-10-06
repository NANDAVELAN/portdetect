---
description: Release or deploy with checks, security review, health check and report
---
1. `git status` must be clean/understood.
2. Run tests.
3. Run lint/type checks.
4. Review the diff.
5. Security check (`security-reviewer`, `.agent/harness/precommit-secrets.sh`).
6. Build artifact/image.
7. Verify the build locally.
8. Confirm the target environment with the user.
9. Release/deploy (`.agent/guardrails/production.md`).
10. Health check.
11. Report exactly what changed and the rollback path.
