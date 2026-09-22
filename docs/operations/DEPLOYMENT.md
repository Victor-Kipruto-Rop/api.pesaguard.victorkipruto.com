# PesaGuard Deployment Architecture

## Runtime packaging

The repository includes Docker assets under `docker/` and infrastructure templates under `infra/`. The Python backend dependencies are managed through multiple requirement snapshots in the `pesaguard_backend_pipeline/` package (`requirements.txt`, `requirements_1.txt`, `requirements_2.txt`, `requirements_3.txt`).

## Local development

Use the workspace virtual environment or install dependencies from the project requirements file before running the Flask routes or testing the pipeline.

## Container model

The repository ships:

- `docker/Dockerfile`
- `docker/Dockerfile.worker`
- `docker/docker-compose.yml`
- `docker/docker-compose.full.yml`

These files map mostly to the infrastructure and deployment model already observed in the repository. The code does not require a full rewrite of the current runtime packaging.

## Environment variables

Production and local runtime settings are driven through environment variables documented in `.env.example` and loaded by modules using `os.getenv(...)` patterns.

## Deployment posture

The project supports staged deployment flows and health checks through `health.py` and route conventions. Operationally, Sentry and Sourcery should remain environment-driven and optional rather than embedded in the code as runtime requirements.
