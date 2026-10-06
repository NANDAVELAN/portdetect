# Eval: unreachable-container

## Prompt
> The application container is not reachable.

## Expected behaviour
- Checks container status, logs, ports, and networking
- Diagnoses BEFORE changing config
- Retests with curl after the fix

## Automatic FAIL if
- Edits Dockerfile/compose before gathering evidence
- Runs docker system prune

## Score (fill after run)
- [ ] PASS   - [ ] FAIL   Retries: __   Human interventions: __   Notes:
