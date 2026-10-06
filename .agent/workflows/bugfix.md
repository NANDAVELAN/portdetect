---
description: Fix a bug via reproduction, root cause, regression test and verification
---
1. Reproduce the failure; capture the exact error/output.
2. Gather evidence (logs, stack trace, recent changes).
3. Identify the root cause (`systematic-debugging`, `debugging`).
4. Write a regression test that FAILS now.
5. Apply the minimal fix.
6. Run the regression test (must pass).
7. Run the full relevant test suite.
8. Review the diff; keep it focused.
9. Verify with real output (`verification-before-completion`).

Do not modify code before understanding the failure unless an immediate
mitigation is required.
