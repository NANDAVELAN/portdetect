---
name: aws-development
description: Use for AWS tasks - EC2, SSH, Security Groups, Elastic IP, Nginx, Docker on EC2, CloudWatch basics, IAM safety, deployment verification.
---

# AWS Development

Follow `.agent/guardrails/production.md` and `security.md`.
NEVER perform destructive production actions automatically.

## Scope
- EC2: launch/inspect instances, key pairs, AMIs, instance state
- SSH: `ssh -i key.pem ubuntu@<ip>`; `chmod 400 key.pem`
- Security Groups: least privilege; no `0.0.0.0/0` on SSH/DB; open only needed ports
- Elastic IP: associate/verify; note cost when unattached
- Nginx: `nginx -t` BEFORE `systemctl reload nginx`; reverse-proxy to app port
- Docker on EC2: install, run, restart policy, logs
- CloudWatch basics: logs, CPU/status-check alarms
- IAM: least privilege, roles over long-lived keys, never print/commit keys

## Deployment verification
1. Confirm target account/region/instance with the user.
2. Deploy.
3. Check service status, logs, listening port.
4. Hit the public endpoint (`curl -i`).
5. Report exactly what changed and how to roll back.

Read-only commands first (`describe-*`, `get-*`, `list-*`); ask before any
`terminate`, `delete`, `revoke`, or `modify` call.
