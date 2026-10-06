---
description: Build, run, diagnose and fix a Dockerized application
---
1. Inspect the application (entrypoint, port, env).
2. Inspect Dockerfile / compose / .dockerignore.
3. Build the image.
4. Run the container.
5. Check logs (redact secrets).
6. Check ports (`docker ps`, `docker port`, bind address).
7. Check networking.
8. Test the endpoint with `curl`.
9. Fix ONE issue based on evidence.
10. Rebuild.
11. Retest and show output.

Follow `.agent/guardrails/docker.md`. Use the `docker-development` skill.
