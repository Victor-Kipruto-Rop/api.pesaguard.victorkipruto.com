# PesaGuard Observability and Code Quality

## Sentry

PesaGuard can ship errors, traces, and performance data to Sentry when the environment exposes a `SENTRY_DSN` and the `sentry-sdk` dependency is installed.

Recommended environment variables:

```bash
export SENTRY_DSN="https://<public-key>@o<org-id>.ingest.sentry.io/<project-id>"
export SENTRY_ENVIRONMENT="development"  # or staging / production
export SENTRY_RELEASE="pesaguard@<git-sha>"
export SENTRY_TRACES_SAMPLE_RATE="0.1"
export SENTRY_PROFILES_SAMPLE_RATE="0.0"
export SENTRY_SEND_DEFAULT_PII="false"
```

Do not commit the DSN or any credentials. Keep them in a local `.env` or the CI secret store only.

The `observability` helper module centralizes Sentry initialization without making the runtime depend on it. Services tag events with safe identifiers such as `service`, `provider`, `environment`, and `component`.

## Sourcery

Sourcery is a developer workflow and pull-request quality layer. It should not be installed as an application runtime dependency. Use the repository-root `.sourcery.yaml` file and a GitHub Actions workflow that runs `sourcery-ai/action` on pull requests to review changed code.

Set the repository secret:

```bash
SOURCERY_TOKEN
```

The workflow in `.github/workflows/sourcery.yml` is the concrete GitHub Actions hook. Review feedback should be allowed to fail without blocking the whole deploy pipeline while a baseline is established.
