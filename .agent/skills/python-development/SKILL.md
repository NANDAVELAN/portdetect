---
name: python-development
description: Use when writing, testing, packaging, or structuring Python code, CLIs, or services (venv, pytest, ruff, typing, logging, env vars).
---

# Python Development

Workflow: Understand → Implement → Test → Lint → Type-check → Review → Verify

## Practices
- Virtual env: `python -m venv .venv`; never install globally.
- Dependencies: pin in `requirements.txt` or `pyproject.toml`; no unused deps.
- Structure: package dir + `tests/`; keep modules small and focused.
- Tests: `pytest -q`; write/adjust tests alongside the change.
- Lint/format: `ruff check .` and `ruff format .`
- Types: `mypy .` or `pyright` on changed modules.
- Logging: use `logging`, not `print`, in libraries/services; never log secrets.
- Errors: catch specific exceptions; no bare `except:`; fail loudly with context.
- CLI: `argparse` or `typer`; `if __name__ == "__main__":` entry.
- Config: read from env (`os.environ`), load `.env` only in dev; commit
  `.env.example`, never `.env`.
- Packaging: `pyproject.toml` with entry points when distributing.

## Verification
Run pytest, ruff, and type-check; report the real output.
