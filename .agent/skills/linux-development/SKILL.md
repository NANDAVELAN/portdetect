---
name: linux-development
description: Use for Linux shell work - filesystem, permissions, processes, services, networking/ports, SSH, logs, package managers, system debugging.
---

# Linux Development

Rule: INSPECT before CHANGING system state. Follow `.agent/guardrails/filesystem.md`.

## Inspect first
- Where am I / what is here: `pwd`, `ls -la`, `df -h`, `du -sh`
- Permissions/ownership: `ls -l`, `stat`, `id`
- Processes: `ps aux | grep`, `top`/`htop`, `pgrep`
- Services: `systemctl status <svc>`, `journalctl -u <svc> -n 100 --no-pager`
- Network/ports: `ss -tulpn`, `ip a`, `curl -v`, `ping`, `dig`
- Logs: `/var/log/*`, `journalctl`, `dmesg | tail`
- Env: `printenv NAME` (single var; never dump all - may hold secrets)
- Packages: `apt list --installed | grep`, `dpkg -L`, `which`, `command -v`

## Changing state
- Prefer least privilege; avoid `sudo` and `chmod 777`.
- Back up config before editing (`cp file file.bak`).
- Make one change, verify, then continue.
- SSH: use keys, correct perms (`chmod 600 key`), never paste private keys.

## Verification
Show the command output that proves the new state (service active, port
listening, file perms correct).
