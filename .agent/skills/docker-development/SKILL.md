---
name: docker-development
description: Use when building, running, debugging, or fixing Docker / Docker Compose setups, unreachable containers, or image build failures.
---

# Docker Development

Follow `.agent/guardrails/docker.md` at all times.

## Process
1. Inspect the project (language, entrypoint, ports, env vars).
2. Detect existing `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
3. Understand dependencies (system packages, runtime, DB/services).
4. Build: `docker build -t <name> .` (read the full error, not just the tail).
5. Run: `docker run --rm -p HOST:CONTAINER <name>`.
6. Logs: `docker logs <container>` (redact secrets).
7. Ports: `docker ps`, `docker port <container>`; app must bind `0.0.0.0`.
8. Networks: `docker network ls/inspect`; check service names / DNS.
9. Test the app: `curl -i http://localhost:PORT/health`.
10. Diagnose from evidence BEFORE editing config.
11. Fix one thing at a time.
12. Rebuild. 13. Retest.
14. Clean up only the resources you created, only when safe.

## "Container not reachable" checklist
status (running/exited) → logs → bound address (0.0.0.0 vs 127.0.0.1) →
port mapping → network/DNS → host firewall → healthcheck.

## Verification
Always show the command output proving the fix (container status + successful
request). Never say "should work".
