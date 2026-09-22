# PesaGuard Development Guide

## Local development

Use the workspace virtual environment and the repository’s Python dependency snapshots to run tests and backend modules from the `pesaguard_backend_pipeline` directory.

## Testing

Repository tests are organized under `tests/` and `pesaguard_backend_pipeline/tests/` and use `pytest`.

## Observability

Sentry is initialized in an optional way via `pesaguard_backend_pipeline/observability.py`. It remains disabled unless `SENTRY_DSN` is present in the environment. This matches the request that the application remain healthy even when observability backends are absent.

## Code quality

A repository-root `.sourcery.yaml` file supports Sourcery review and quality configuration.

## Security

Do not commit real secrets. Keep them in environment variables or project-level secret stores.
