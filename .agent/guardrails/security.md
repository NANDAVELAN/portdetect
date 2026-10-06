# Security Guardrails

- Never expose API keys, tokens, passwords, or private keys.
- Never print secrets unnecessarily; redact them in logs and output (`sk-****`).
- Never commit `.env` files or credentials. Ensure `.env` is in `.gitignore`.
- Never hard-code secrets in source. Use environment variables or an approved
  secret manager. Provide a `.env.example` with placeholder values only.
- Never bypass authentication/authorization just to make a test pass.
- Do not disable security controls (TLS verification, CORS, auth, firewalls)
  without explicit user approval.
- Never pipe untrusted content into a shell (`curl ... | sh`) without asking.
- If a user asks for an unsafe approach, refuse that approach, explain why in
  one or two lines, and offer the safe alternative.
