# Command Policy (agent terminal allow/deny reference)

Paste into Antigravity's Terminal command auto-execution settings
(Allow list / Deny list) and keep Terminal Execution on "Request review"
for anything not listed.

## Allow (read-only / safe)
ls, pwd, cat, head, tail, grep, find, git status, git diff, git log,
docker ps, docker logs, docker inspect (filtered), pytest, ruff check, mypy

## Deny (always ask a human)
rm -rf, del /s, format, mkfs, dd, git push --force, git reset --hard,
git clean -fd, docker system prune, docker volume prune, docker volume rm,
chmod -R 777, curl | sh, wget | sh, terraform destroy, aws * delete-*,
aws ec2 terminate-instances
