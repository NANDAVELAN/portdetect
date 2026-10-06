---
name: debugging
description: Use when something fails or behaves unexpectedly. Evidence-driven loop that complements systematic-debugging; forbids random trial-and-error edits.
---

# Debugging

Observe → Reproduce → Gather evidence → Form hypothesis → Test hypothesis
→ Fix → Regression test → Verify

## Rules
- No code changes before you can reproduce, unless an immediate mitigation is
  required (state it as a mitigation).
- Write the hypothesis down: "I believe X because Y; I will check by Z."
- Change ONE variable at a time; revert failed experiments.
- Keep a short log: attempt → result → conclusion.
- After 3 failed hypotheses, stop and re-read the evidence / ask the user.
- Every fix gets a regression test that fails before and passes after.
- Report the root cause, not just "it works now".

Use together with `systematic-debugging` and `test-driven-development`.
