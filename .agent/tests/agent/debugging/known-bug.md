# Eval: known-bug

## Prompt
> Fix this known bug: <describe a bug in your repo>.

## Expected behaviour
- Reproduces the bug first
- Adds a regression test that fails before the fix
- Fixes, then runs the test and the full suite

## Automatic FAIL if
- Edits code before reproducing
- Random trial-and-error changes
- No regression test

## Score (fill after run)
- [ ] PASS   - [ ] FAIL   Retries: __   Human interventions: __   Notes:
