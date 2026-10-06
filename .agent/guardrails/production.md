# Production Guardrails

Production actions need a higher safety level. Before deployment:
1. Run tests.
2. Review the diff.
3. Validate configuration.
4. Check environment variables (names only; never print values).
5. Confirm the TARGET environment with the user.
6. Perform the deployment.
7. Verify health (health endpoint, logs, smoke test).
8. Report exactly what changed.

Never destroy production infrastructure automatically (terminate instances,
delete databases/buckets/volumes, remove security groups, rotate or delete
IAM keys). Always prefer reversible steps and keep a rollback path.
