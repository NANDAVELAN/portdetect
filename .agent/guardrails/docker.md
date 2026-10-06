# Docker Guardrails

NEVER run automatically (explicit approval required):
- `docker system prune -a`
- `docker volume prune`, `docker volume rm`
- `docker rm -f` / `docker rmi -f` on things you did not create

Before deleting containers, images, networks, or volumes:
- Identify what depends on them (`docker ps -a`, `docker network inspect`,
  `docker volume ls`, compose files).
- Explain the impact.
- Prefer targeted cleanup (one named resource) over broad prune.

Do not expose secrets via `docker inspect`, `docker logs`, `env`, or
`docker compose config`. Filter or redact environment variables in output.
Never run containers with `--privileged` or mount the Docker socket unless the
user explicitly requires it.
