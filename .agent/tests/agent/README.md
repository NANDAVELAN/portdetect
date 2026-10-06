# Agent Evals

1. Start a fresh Antigravity conversation.
2. Paste the **Prompt** from a case file.
3. Judge the run against *Expected* / *Automatic FAIL*.
4. Record: `bash .agent/tests/agent/score.sh full coding/add-function-with-tests pass 0 0 "clean"`
5. Repeat each case under each setup and compare results.csv:
   baseline -> superpowers -> +skills -> +guardrails -> full

Metrics: success rate, test pass rate, retries, human interventions,
incorrect modifications, destructive actions, security violations,
false claims of completion, time, token usage.
