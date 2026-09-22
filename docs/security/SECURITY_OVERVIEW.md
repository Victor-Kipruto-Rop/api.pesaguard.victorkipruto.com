# PesaGuard Security Architecture

PesaGuard already contains several security primitives in the repository, including request validation, authentication/RBAC helpers, rate limiting, webhook source restrictions, and environment-based configuration. This document reflects the security controls the codebase currently contains rather than inventing new controls.

## Existing controls observed

- Flask route protection and admin-token checks in `app.py`.
- JWT, RBAC and role enforcement helpers in `auth_rbac.py`, `rbac.py`, and related files.
- Rate limiting in `rate_limiter.py`.
- Webhook source validation and request-size helpers in `security_helpers.py` and shared validators.
- Environment-driven configuration for secrets and credentials using `.env.example` and `.env`-style secret storage.
- Dependency and security scan workflows in `.github/workflows/dependency-scan.yml`.

## Recommended security posture

- Do not commit real secrets or DSNs.
- Store `SENTRY_DSN`, `SOURCERY_TOKEN`, provider credentials, and deployment secrets externally in the runtime environment or CI secret store.
- Keep `send_default_pii=False` in Sentry configuration.
- Do not log credentials, PINs, API keys, authorization headers, cookies, or tokens.
- Continue to treat webhook payloads as untrusted and validate source, format, and signatures where available.

## Security areas that remain external or future

The repository shows JWT, RBAC, and request validation support, but not a full enterprise-grade MFA, Vault integration, or full per-tenant RBAC policy engine. Those are documented as operational and deployment future work rather than being claimed as implemented.
