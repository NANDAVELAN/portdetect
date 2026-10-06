#!/usr/bin/env bash
# Blocks commits that contain likely secrets or tracked .env files.
# Install:  cp .agent/harness/precommit-secrets.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
set -uo pipefail
fail=0

if git diff --cached --name-only | grep -Eq '(^|/)\.env($|\.)' ; then
  if git diff --cached --name-only | grep -E '(^|/)\.env($|\.)' | grep -qv '\.example$'; then
    echo "BLOCKED: .env file staged"; fail=1
  fi
fi

PATTERN='(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|(api[_-]?key|secret|passwd|password|token)[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"']{8,}["'"'"'])'
if git diff --cached -U0 | grep -E '^\+' | grep -Eiq "$PATTERN"; then
  echo "BLOCKED: possible secret in staged changes:"
  git diff --cached -U0 | grep -E '^\+' | grep -Ei "$PATTERN" | sed -E 's/(.{60}).*/\1.../'
  fail=1
fi

[[ $fail -eq 0 ]] && echo "secret scan: OK"
exit $fail
